"""
Unit tests for the courlan package: check_url, link extraction and network.
"""

import logging
import os
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import pytest
from urllib3.util.retry import RequestHistory, Retry

from courlan import (
    check_url,
    clean_url,
    extract_links,
    normalize_url,
    validate_url,
)
from courlan.core import MAX_RAW_LENGTH, _host_parts, filter_links
from courlan.hosts import get_registrable_domain
from courlan.meta import clear_caches
from courlan.network import redirection_test
from courlan.urlutils import _parse


def test_urlcheck():
    assert check_url("AAA") is None
    assert check_url("1234") is None
    assert check_url("http://ab") is None
    assert check_url("ftps://example.org/") is None
    assert check_url("http://t.g/test") is None
    assert check_url(
        "https://www.dwds.de/test?param=test&amp;other=test", strict=True
    ) == ("https://www.dwds.de/test", "dwds.de")
    assert check_url("http://example.com/index.html#term", strict=True) is None
    result = check_url("http://example.com/index.html#term", strict=False)
    assert result is not None and result[0] == "http://example.com/index.html#term"
    assert check_url("http://example.com/test.js") is None
    assert check_url("http://twitter.com/", strict=True) is None
    assert check_url("http://twitter.com/", strict=False) is not None
    # basic_filter sees the scrubbed URL, in any case
    for url in (
        " https://example.org/a",
        "HTTPS://example.org/a",
        "Http://example.org/a",
    ):
        assert check_url(url) == ("https://example.org/a", "example.org") or check_url(
            url
        ) == ("http://example.org/a", "example.org")
    # no host is made of a host with a space or a "%"
    for url in ("https://exa mple.org", "https://exa%20mple.org", "http://Du%20bist"):
        assert validate_url(url) == (False, None)
    assert validate_url(" https://example.org ")[1] == urlsplit("https://example.org")


@pytest.mark.parametrize(
    "url, kwargs, reason",
    [
        ("ftp://x", {}, "basic filter"),
        ("https://ab", {}, "validation test"),
        ("https://exa_.org/", {}, "domain name"),
        ("https://example.org/a.docx", {}, "extension filter"),
        ("https://example.org/tag/x", {}, "type filter"),
        ("https://example.org/a?utm_source=x/tag/y/", {}, "type filter"),
        ("https://example.org/index.html", {"strict": True}, "path filter"),
        ("https://example.org/fr/a", {"language": "de"}, "lang filter"),
        ("https://example.org/a?lang=en", {"language": "de"}, "lang param"),
        ("https://twitter.com/a", {"strict": True}, "domain name"),
        (5, {}, "input"),
    ],
)
def test_urlcheck_rejection_trace(caplog, url, kwargs, reason):
    "Each rejection logs the step that made it."
    with caplog.at_level(logging.DEBUG, logger="courlan.core"):
        assert check_url(url, **kwargs) is None
        assert f"rejected, {reason}:" in caplog.text


def test_urlcheck_type_and_spam():
    "Recheck type and spam filters through check_url."
    assert check_url("http://example.org/wp-json/oembed/") is None
    assert check_url("http://livecams.com/", strict=False) == (
        "http://livecams.com",
        "livecams.com",
    )
    assert check_url("http://livecams.com/", strict=True) is None
    assert check_url("https://denkiterm.wordpress.com/impressum/", strict=True) is None
    assert (
        check_url(
            "http://www.fischfutter-index.de/improvit-trocken-frostfutter-fur-fast-alle-fische/",
            strict=True,
        )
        is not None
    )
    # feeds are rejected whether or not the path keeps its trailing slash
    for url in (
        "http://example.org/feed/",
        "http://example.org/rss/",
        "http://example.org/feed/#f",
        "http://example.org/feed?x=1",
    ):
        assert check_url(url) is None
        assert check_url(url, trailing_slash=False) is None

    # patterns hidden in the query or the fragment, which normalization removes
    assert check_url("https://example.org/page?file=movie.mp4", strict=True) is None
    assert (
        check_url("http://example.org/page?utm_source=a&file=b.mp4", strict=True)
        is None
    )
    assert check_url("http://example.org/page#movie.mp4", strict=True) is None
    assert check_url("https://example.org/page?p=/tags/x/") is None
    assert check_url("https://example.org/page?next=/wp-admin/") is None

    # patterns normalization creates itself, seen only on the final form
    assert check_url("http://example.org/tags//x/") is None
    assert check_url("http://example.org//tags//x/") is None
    assert check_url("http://example.org/category//123/") is None
    assert check_url("http://example.org/tags/x/?") is None


def test_urlcheck_language():
    "Test language and internationalization handling in check_url."
    assert check_url("http://example.com/test.html?lang=en", language="de") is None
    assert check_url("http://example.com/test.html?lang=en", language=None) is not None
    assert check_url("http://example.com/test.html?lang=en", language="en") is not None
    # a language param without value doesn't reject the URL, and doesn't hide one
    assert check_url("http://example.com/test.html?lang=&id=3", language="en") == (
        "http://example.com/test.html?id=3",
        "example.com",
    )
    assert check_url("http://example.com/test.html?lang&id=3", language="en") == (
        "http://example.com/test.html?id=3&lang",
        "example.com",
    )
    assert (
        check_url("http://example.com/test.html?lang=&lang=de", language="en") is None
    )
    assert check_url("http://example.com/de/test.html", language="de") is not None
    assert check_url("http://example.com/en/test.html", language="de") is None
    assert check_url("http://example.com/en/test.html", language=None) is not None
    assert check_url("http://example.com/en/test.html", language="en") is not None
    # strict mode checks the host language cue
    assert check_url("https://en.wikipedia.org/", strict=True, language="de") is None
    assert (
        check_url(
            "https://www.myswitzerland.com/de-ch/erlebnisse/veranstaltungen/wild-im-sternen/",
            language="de",
        )
        is not None
    )
    assert (
        check_url(
            "https://www.myswitzerland.com/en-id/accommodations/other-types-of-accommodations/on-the-farm/farm-experiences-search/",
            language="en",
        )
        is not None
    )
    assert (
        check_url(
            "https://www.myswitzerland.com/EN-ID/accommodations/other-types-of-accommodations/on-the-farm/farm-experiences-search/",
            language="en",
        )
        is not None
    )
    # impressum and index
    assert check_url("http://www.example.org/index", strict=True) is None
    assert check_url("http://www.example.org/index.html", strict=True) is None
    assert check_url("http://concordia-hagen.de/impressum.html", strict=True) is None
    assert check_url("http://concordia-hagen.de/de/impressum", strict=True) is None
    # repeated slashes are collapsed before the path filter is applied
    assert check_url("http://www.example.org/home//", strict=True) is None
    assert check_url("http://concordia-hagen.de/impressum//", strict=True) is None
    assert (
        check_url("http://parkkralle.de/detail/index/sArticle/2704", strict=True)
        is not None
    )
    assert (
        check_url(
            "https://www.katholisch-in-duisdorf.de/kontakt/links/index.html",
            strict=True,
        )
        is not None
    )
    assert check_url("{mylink}") is None
    assert (
        check_url(
            "https://de.nachrichten.yahoo.com/bundesliga-schiri-boss-fr%C3%B6hlich-f%C3%BCr-175850830.html",
            language="de",
        )
        is not None
    )
    assert (
        check_url(
            "https://de.nachrichten.yahoo.com/bundesliga-schiri-boss-fr%C3%B6hlich-f%C3%BCr-175850830.html",
            language="de",
            strict=True,
        )
        is None
    )
    assert (
        check_url(
            "https://de.nachrichten.other.com/bundesliga-schiri-boss-fr%C3%B6hlich-f%C3%BCr-175850830.html",
            language="en",
        )
        is not None
    )
    assert (
        check_url(
            "https://de.nachrichten.other.com/bundesliga-schiri-boss-fr%C3%B6hlich-f%C3%BCr-175850830.html",
            language="en",
            strict=True,
        )
        is None
    )


def test_urlcheck_domain():
    "Test domain and host name validation through check_url."
    assert check_url("http://-100x100.webp") is None
    assert check_url("http://0.gravata.html") is None
    assert check_url("http://https:") is None
    assert check_url("http://127.0.0.1") is not None
    assert check_url("http://111.111.111.111") is not None
    assert check_url("http://0127.0.0.1") is None
    assert check_url("http://2001:0db8:85a3:0000:0000:8a2e:0370:7334") is not None
    # bracketed form is what urlsplit produces for a valid IPv6 URL
    assert check_url("http://[2001:0db8:85a3:0000:0000:8a2e:0370:7334]") == (
        "http://[2001:db8:85a3::8a2e:370:7334]",
        "2001:db8:85a3::8a2e:370:7334",
    )
    assert check_url("http://[2001:db8::1]/page") == (
        "http://[2001:db8::1]/page",
        "2001:db8::1",
    )
    assert check_url("http://1:2:3:4:5:6:7:8:9") is None
    # a bare public suffix is its own domain
    assert check_url("https://a.ck/page") == ("https://a.ck/page", "a.ck")
    assert check_url("https://gov.uk/browse/benefits") == (
        "https://gov.uk/browse/benefits",
        "gov.uk",
    )
    # trailing-dot FQDN URLs are valid and normalized to the dotless form
    assert check_url("http://example.com./page") == (
        "http://example.com/page",
        "example.com",
    )
    assert check_url("http://192.168.0.1./x") == (
        "http://192.168.0.1/x",
        "192.168.0.1",
    )
    assert check_url("http://example.com../page") is None


def test_urlcheck_fixed_point():
    "check_url is idempotent: re-checking its own output changes nothing."
    urls = [
        "http://test.org/?s_cid=123&clickid=1",
        "http://test.org/?utm_source=&utm_medium=",
        "http://test.org/#partnerid=123",
        "https://example.org/?",
        "http://EXAMPLE.org:80/a//b/?page=2#frag",
        "https://example.org/index.html?document=report.pdf",
        "http://www.example.org/path/?utm_source=x",
        "https://example.org/datenschutzerklärung",
        "http://de.example.org/en/page/",
        "http://xn--nxasmq6b.com:8080/feed",
        "http://test.org/page?article8532",
        "http://test.org/page?download&x=1",
        "http://test.org/page?a=&b=2",
        "http://test.org/page?a=",
        "http://test.org/page?page&other",
        "http://test.org/page?page=&id=3",
        "http://test.org/page?lang=&id=3",
        "http://test.org/page?lang&id=3",
        "http://test.org/page?q=M%FCnchen",
        "http://test.org/page?M%FCnchen",
        "http://test.org/page#a=&view=grid",
        "http://test.org/page#b&a=M%FC",
        "https://www.facebook.com/MIXED.de/",
        "https://example.org/report.pdf/",
        "https://www.pinterest.com/pin/create/button/?url=https://ex.org/a&#038;media=https://ex.org/b.jpg&#038;description=x",
        "https://web.archive.org/web/2016/http://www.welpenkaufen24.de/",
        "https://example.org/a/%c3%a9/%40user/C%2b%2b",
        # the fragment separators stay, a second pass reads the same params
        "https://example.org/t#a=b&c=d{g/open-source/",
        # bare keys left alone, a value read as a tracker
        "https://example.org/p#utm_source=x&a&b",
        "https://example.org/p#tab=source&utm_medium=x",
    ]
    for url in urls:
        for config in CONFIGS:
            first = check_url(url, **config)
            if first:
                assert check_url(first[0], **config) == first, (url, config)


CONFIGS: tuple[dict[str, Any], ...] = (
    {"strict": False},
    {"strict": True},
    {"strict": False, "language": "de"},
    {"strict": True, "language": "en"},
    {"strict": False, "trailing_slash": False},
    {"strict": True, "trailing_slash": False},
)


@pytest.mark.parametrize(
    "url",
    [
        "https://crazy-julia.de/das-leben-in-einem-tag/",
        "https://example.org/tag/news",
        "https://example.org/2024/05/",
        "https://www.facebook.com/MIXED.de/",
        "https://example.org/report.pdf/",
        "https://example.org/index.html",
        "https://example.org/a?b=1",
        "https://example.org?next=/",
        "https://web.archive.org/web/2016/http://www.welpenkaufen24.de/",
        "https://reddit.com/submit?url=https://example.org/blog/x/&title=T",
        "https://www.sitemaps.org/fr/",
    ],
)
def test_urlcheck_variant_invariance(url):
    "A tracker or a bare '?' does not change the result."
    variants = [url + ("&" if "?" in url else "?") + "utm_source=x"]
    if "?" not in url:
        variants.append(url + "?")
    for config in CONFIGS:
        expected = check_url(url, **config)
        for variant in variants:
            assert check_url(variant, **config) == expected, (variant, config)
        # without trailing slashes, both forms of a path are one URL,
        # except for dates, which need the slash: "/2024/05" is no archive page
        if not config.get("trailing_slash", True) and "?" not in url:
            other = url.rstrip("/") if url.endswith("/") else url + "/"
            if "/2024/05" in url:
                assert expected is None and check_url(other, **config), config
            else:
                assert check_url(other, **config) == expected, (other, config)


def test_urlcheck_dates_without_slash():
    "Date archives are rejected before the slash is stripped, except navigation."
    url = "https://example.org/category/2024/05/"
    assert check_url(url, trailing_slash=False) is None
    assert check_url(url, trailing_slash=False, with_nav=True) == (
        url[:-1],
        "example.org",
    )
    # with a query the slash stays, so the path is checked as it is
    for url in (
        "https://example.org/2024/05/?a=1",
        "https://example.org/report.pdf/?a=1",
    ):
        assert check_url(url, trailing_slash=False) == (url, "example.org")
    assert (
        check_url("https://example.org/report.pdf/?utm_source=x", trailing_slash=False)
        is None
    )


def test_urlcheck_raw_length():
    "Long raw input is rejected before scrubbing, even if scrubbing would shorten it."
    core = "https://example.org/a" + "<b>" * 600
    url = " " * (MAX_RAW_LENGTH - len(core)) + core
    assert check_url(url) == ("https://example.org/a", "example.org")
    assert check_url(" " + url) is None


@pytest.mark.xfail(reason="item 29, a terminal language segment is no cue")
def test_urlcheck_terminal_language_segment():
    assert check_url("https://www.sitemaps.org/da/", language="de") is None
    assert check_url("https://www.sitemaps.org/da", language="de") is None


def test_urlcheck_port():
    "Test port handling through check_url."
    assert check_url("http://example.com:80") is not None
    assert check_url("http://example.com:80:80") is None
    # IPv4 host with a port must not be rejected as a bad domain
    assert check_url("http://127.0.0.1:8080/x") is not None
    # out-of-range port on an IPv4 host is rejected like the domain form
    assert check_url("http://1.2.3.4:99999/x") is None
    # bracketed IPv6 with a port (urlsplit netloc shape)
    assert check_url("http://[::1]:8080/x") == ("http://[::1]:8080/x", "::1")
    assert check_url("http://[::1]:99999/x") is None
    # IDN host with a port
    assert check_url("http://xn--h1aagokeh.xn--p1ai:8888") == (
        "http://историк.рф:8888",
        "историк.рф",
    )


def test_urlcheck_redirects():
    "Test redirection checks with a mocked HTTP pool."

    def _fake_head(status, location=None):
        resp = MagicMock()
        resp.status = status
        hops = (RequestHistory("HEAD", "https://a.org/", None, 302, location),)
        resp.retries = Retry(history=hops if location else ())
        return resp

    with patch("courlan.network.HTTP_POOL.request") as mock_request:
        # acceptable status code: resolve to the final URL
        mock_request.return_value = _fake_head(200, "http://example.org")
        assert check_url(
            "https://httpbun.org/redirect-to?url=http%3A%2F%2Fexample.org",
            with_redirects=True,
        ) == ("http://example.org", "example.org")
        # unacceptable status code: rejected
        mock_request.return_value = _fake_head(404)
        assert check_url("https://httpbun.org/status/404", with_redirects=True) is None
        # transport failure: redirection_test raises ValueError, check_url returns None
        mock_request.side_effect = Exception("unreachable")
        assert check_url("https://www.ht.or", with_redirects=True) is None
        # no redirect: the input URL is kept
        mock_request.side_effect = None
        mock_request.return_value = _fake_head(200)
        assert check_url("http://example.org/page", with_redirects=True) == (
            "http://example.org/page",
            "example.org",
        )
        # unicode hosts are requested in punycode
        assert check_url("https://bücher.de/a", with_redirects=True) == (
            "https://bücher.de/a",
            "bücher.de",
        )
        assert mock_request.call_args.args == ("HEAD", "https://xn--bcher-kva.de/a")


@contextmanager
def _serve(routes):
    "Serve HEAD requests from {path: [(status, location), ...]}, the last pair repeats."
    log = []

    class Handler(BaseHTTPRequestHandler):
        def do_HEAD(self):
            log.append(self.path)
            replies = routes.get(self.path, [(404, None)])
            status, location = replies.pop(0) if len(replies) > 1 else replies[0]
            self.send_response(status)
            if location:
                self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", log
    finally:
        server.shutdown()
        server.server_close()


def test_redirection():
    "Test redirection_test against local HTTP servers (no external network)."
    with _serve({"/y": [(302, "/z")], "/z": [(200, None)]}) as (other, _):
        routes = {
            "/final": [(200, None)],
            "/rel": [(301, "sub/page")],
            "/sub/page": [(200, None)],
            "/x": [(302, f"{other}/y")],
            "/moved": [(302, "/flaky")],
            "/flaky": [(503, None), (200, None)],
            "/c1": [(302, "/c2")],
            "/c2": [(302, "/c3")],
            "/c3": [(302, "/c4")],
            "/c4": [(200, None)],
        }
        with _serve(routes) as (base, log):
            routes["/redirect"] = [(302, f"{base}/final")]
            assert redirection_test(f"{base}/redirect") == f"{base}/final"
            # no redirect: urllib3 reports the bare request path
            assert redirection_test(f"{base}/final") == f"{base}/final"
            assert redirection_test(f"{base}/rel") == f"{base}/sub/page"
            # relative Location after a cross-host hop resolves against the second host
            assert redirection_test(f"{base}/x") == f"{other}/z"
            # a status retry after a redirect keeps the redirect target
            assert redirection_test(f"{base}/moved") == f"{base}/flaky"
            assert log.count("/flaky") == 2
            # 2 redirects at most: the 3rd URL is returned, its redirect is not followed
            assert redirection_test(f"{base}/c1") == f"{base}/c3"
            assert "/c4" not in log
            with pytest.raises(ValueError):
                redirection_test(f"{base}/missing")


def test_extraction():
    """test link comparison in HTML"""
    with pytest.raises(ValueError):
        extract_links(None, base_url="https://test.com/", external_bool=False)  # type: ignore[arg-type]
    assert not extract_links(None, url="https://test.com/", external_bool=False)  # type: ignore[arg-type]
    assert not extract_links("", "https://test.com/", False)
    # anchor tags matched by the regex but without an href yield no candidate
    pagecontent = '<html><a class="logo">home</a><a name="x">y</a></html>'
    assert not extract_links(pagecontent, "https://test.com/", False)
    # hreflang matches the target language but the tag has no href
    pagecontent = '<html><a hreflang="de-DE">no href</a></html>'
    assert not extract_links(pagecontent, "https://test.com/", False, language="de")
    # empty quoted href must not capture the closing quote as a path (/%27)
    pagecontent = "<html><a href=''>x</a></html>"
    assert extract_links(pagecontent, "https://example.org", False) == [
        "https://example.org"
    ]
    assert extract_links(pagecontent, "https://example.org", no_filter=True) == [
        "https://example.org"
    ]
    pagecontent = '<html><a href="">x</a></html>'
    assert extract_links(pagecontent, "https://example.org", False) == [
        "https://example.org"
    ]
    assert extract_links(pagecontent, "https://example.org", no_filter=True) == [
        "https://example.org"
    ]
    # link known under another form
    pagecontent = '<html><a href="https://test.org/example"/><a href="https://test.org/example/&"/></html>'
    assert extract_links(pagecontent, "https://test.org", False) == [
        "https://test.org/example"
    ]
    # nofollow
    pagecontent = '<html><a href="https://test.com/example" rel="nofollow ugc"/></html>'
    assert not extract_links(pagecontent, "https://test.com/", False)
    pagecontent = '<html><a href="https://test.com/rel/nofollow-guide"/></html>'
    assert extract_links(pagecontent, "https://test.com/", False) == [
        "https://test.com/rel/nofollow-guide"
    ]
    # language
    example = ["https://test.com/example"]
    pagecontent = '<html><a href="https://test.com/example" hreflang="de-DE"/></html>'
    assert extract_links(pagecontent, "https://test.com/", False) == example
    assert not extract_links(pagecontent, "https://test.com/", True)
    assert (
        extract_links(pagecontent, "https://test.com/", False, language="de") == example
    )
    assert not extract_links(pagecontent, "https://test.com/", False, language="en")
    pagecontent = "<html><a href=https://test.com/example hreflang=de-DE/></html>"
    assert (
        extract_links(pagecontent, "https://test.com/", False, language="de") == example
    )
    # x-default
    pagecontent = (
        '<html><a href="https://test.com/example" hreflang="x-default"/></html>'
    )
    assert (
        extract_links(pagecontent, "https://test.com/", False, language="de") == example
    )
    assert (
        extract_links(pagecontent, "https://test.com/", False, language="en") == example
    )
    pagecontent = '<html><a href="https://test.com/example" hreflang="DE-DE"/></html>'
    assert (
        extract_links(pagecontent, "https://test.com/", False, language="de") == example
    )
    assert not extract_links(pagecontent, "https://test.com/", False, language="en")
    pagecontent = (
        '<html><a href="https://test.com/example" hreflang="X-DEFAULT"/></html>'
    )
    assert (
        extract_links(pagecontent, "https://test.com/", False, language="de") == example
    )
    # language + content
    pagecontent = '<html><a hreflang="de-DE" href="https://test.com/example"/><a href="https://test.com/example2"/><a href="https://test.com/example3 ADDITIONAL"/></html>'
    links = extract_links(pagecontent, "https://test.com/", external_bool=False)
    # a quoted href keeps its inner space, encoded
    assert links == [
        "https://test.com/example",
        "https://test.com/example2",
        "https://test.com/example3%20ADDITIONAL",
    ]
    assert extract_links(pagecontent, "https://test.com/", language="de") == links
    pagecontent = '<html><a hreflang="de-DE" href="https://test.com/example"/><a href="https://test.com/page/2"/></html>'
    assert extract_links(pagecontent, "https://test.com/", with_nav=False) == example
    assert extract_links(pagecontent, "https://test.com/", with_nav=True) == [
        "https://test.com/example",
        "https://test.com/page/2",
    ]
    # filtered, invalid or duplicate links must not stop extraction of later ones
    pagecontent = '<html><a href="https://test.com/skip" rel="nofollow"/><a href="https://test.com/keep"/></html>'
    assert extract_links(pagecontent, "https://test.com/") == ["https://test.com/keep"]
    pagecontent = '<html><a href="http://t.g/x"/><a href="https://test.com/ok"/></html>'
    assert extract_links(pagecontent, "https://test.com/") == ["https://test.com/ok"]
    pagecontent = '<html><a href="https://test.com/a"/><a href="https://test.com/a"/><a href="https://test.com/b"/></html>'
    assert extract_links(pagecontent, "https://test.com/") == [
        "https://test.com/a",
        "https://test.com/b",
    ]


@pytest.mark.parametrize(
    "anchor, expected",
    [
        # entities, decoded with or without filters
        ('<a href="/p?type&#x3D;news&amp;a=1">', "/p?a=1&type=news"),
        ('<a href="/p?a=1&#038;cpage=2">', "/p?a=1&cpage=2"),
        # unquoted values end at any whitespace
        ("<a href=/a\nclass='x'>", "/a"),
        ("<a href=/a\tclass='x'>", "/a"),
        ("<a href=/a>", "/a"),
        # the href attribute, not data-href or ng-href
        ('<a data-href="/no" href="/a">', "/a"),
        ('<a ng-href="/no" href="/a">', "/a"),
        ('<a href = "/a">', "/a"),
        ("<a HREF='/a'>", "/a"),
        ('<a href=" /a ">', "/a"),
        ('<a class="x"href="/a">', "/a"),
        ('<a :href="loginLink">', None),
        ('<a xlink:href="/svg">', "/svg"),
        # not a name inside another value
        ('<a onclick="location.href=\'/js\'" href="/a">', "/a"),
        ('<a data-track="x&href=/no" href="/a">', "/a"),
        ('<a href="/a?rel=nofollow">', "/a?rel=nofollow"),
        ('<a href="/a?hreflang=fr">', "/a?hreflang=fr"),
        # script-built anchors end at the other quote
        ("<a href=\"/a' + posturl + '\">", "/a"),
        # a share link keeps the embedded URL past its inner space
        (
            '<a href="https://twitter.com/intent/tweet?text=A title&url=https://test.com/a">',
            "/a",
        ),
        # nofollow in the rel attribute only, in any case
        ('<a href="/nofollow-policy" rel="author">', "/nofollow-policy"),
        ('<a href="/a" REL="NOFOLLOW">', None),
        ('<a href="/a" rel="nOfOlLoW">', None),
        ('<a rel="noopener nofollow" href="/a">', None),
        ("<a href=/a rel=nofollow>", None),
        ('<a href="/a"rel="nofollow">', None),
        # hreflang as an attribute only
        ('<a href="/blog/hreflang-guide">', "/blog/hreflang-guide"),
        ('<a href="/a" hreflang="fr">', None),
        ('<a href="/a" hreflang="en-GB">', "/a"),
        ('<a href="/a" HREFLANG="fr">', None),
    ],
)
def test_extraction_attributes(anchor, expected):
    "The href, rel and hreflang attributes are read as attributes."
    expected = [f"https://test.com{expected}"] if expected else []
    assert (
        extract_links(anchor, "https://test.com", language="en", strict=False)
        == expected
    )


def test_extraction_entities_no_filter():
    "Entities are decoded without the filters too."
    assert extract_links(
        '<a href="/p?type&#x3D;news&amp;a=1">', "https://test.com", no_filter=True
    ) == ["https://test.com/p?type=news&a=1"]


def test_extraction_unresolvable(caplog):
    """links failing to resolve are dropped and logged, even without filters"""
    pagecontent = '<html><a href="/a">x</a><a href="https://ok.org/z">z</a></html>'
    with caplog.at_level(logging.DEBUG, logger="courlan.core"):
        links = extract_links(pagecontent, url="http://[::1", no_filter=True)
    assert links == ["https://ok.org/z"]
    assert "unresolvable link: /a" in caplog.text


def test_extraction_navigation():
    "Test link extraction for navigation and CMS edge cases."
    pagecontent = "<html><head><title>Links</title></head><body><a href='/links/2/0'>0</a> <a href='/links/2/1'>1</a> </body></html>"
    links = extract_links(
        pagecontent, "https://httpbun.org", external_bool=False, with_nav=True
    )
    assert links == [
        "https://httpbun.org/links/2/0",
        "https://httpbun.org/links/2/1",
    ]
    pagecontent = "<html><head><title>Links</title></head><body><a href='links/2/0'>0</a> <a href='links/2/1'>1</a> </body></html>"
    links = extract_links(
        pagecontent,
        url="https://httpbun.org/page1/",
        external_bool=False,
        with_nav=True,
    )
    assert links == [
        "https://httpbun.org/page1/links/2/0",
        "https://httpbun.org/page1/links/2/1",
    ]
    pagecontent = "<html><head><title>Pages</title></head><body><a href='/page/10'>10</a> <a href='/page/?=11'>11</a></body></html>"
    assert (
        extract_links(
            pagecontent,
            "https://example.org",
            external_bool=False,
            strict=False,
            with_nav=False,
        )
        == []
    )
    links = extract_links(
        pagecontent,
        "https://example.org",
        external_bool=False,
        strict=True,
        with_nav=True,
        trailing_slash=True,
    )
    assert links == [
        "https://example.org/page/10",
        "https://example.org/page/",
    ]
    links = extract_links(
        pagecontent,
        "https://example.org",
        external_bool=False,
        strict=True,
        trailing_slash=False,
        with_nav=True,
    )
    assert links == [
        "https://example.org/page/10",
        "https://example.org/page",  # parameter stripped by strict filtering
    ]
    links = extract_links(
        pagecontent,
        "https://example.org",
        external_bool=False,
        strict=False,
        with_nav=True,
    )
    assert links == [
        "https://example.org/page/10",
        "https://example.org/page/?=11",
    ]
    # links undeveloped by CMS
    pagecontent = (
        '<html><a href="{privacy}" target="_privacy">{privacy-link}</a></html>'
    )
    assert not extract_links(pagecontent, "https://test.com/", external_bool=False)
    assert not extract_links(pagecontent, "https://test.com/", external_bool=True)
    # links without quotes
    pagecontent = "<html><a href=/link>Link</a></html>"
    assert extract_links(pagecontent, "https://test.com/", external_bool=False) == [
        "https://test.com/link"
    ]
    assert extract_links(pagecontent, "https://test.com/", external_bool=True) == []
    pagecontent = "<html><a href=/link attribute=value>Link</a></html>"
    assert extract_links(pagecontent, "https://test.com/", external_bool=False) == [
        "https://test.com/link"
    ]
    # external links with extension (here ".com")
    pagecontent = '<html><body><a href="https://knoema.com/o/data-engineer-india"/><a href="https://knoema.recruitee.com/"/></body></html>'
    assert extract_links(pagecontent, "https://knoema.com/", external_bool=False) == [
        "https://knoema.com/o/data-engineer-india"
    ]
    assert extract_links(pagecontent, "https://knoema.com/", external_bool=True) == [
        "https://knoema.recruitee.com"
    ]
    # without url, external_bool must not filter (no reference to compare)
    pagecontent = '<html><a href="https://example.com/page"/><a href="https://other.org/post"/></html>'
    expected = ["https://example.com/page", "https://other.org/post"]
    assert extract_links(pagecontent) == expected
    assert extract_links(pagecontent, external_bool=True) == expected
    # return all links without filters
    pagecontent = '<html><a hreflang="de-DE" href="https://test.com/example"/><a href="/page/2"/><a href="https://example.com/gallery/"/></html>'
    result = extract_links(
        pagecontent, "https://test.com", external_bool=True, no_filter=True
    )
    assert result == [
        "https://test.com/example",
        "https://test.com/page/2",
        "https://example.com/gallery/",
    ]


def test_filter_links():
    base_url = "https://example.org"
    htmlstring = '<html><body><a href="https://example.org/page1"/><a href="https://example.org/page1/"/><a href="https://test.org/page1"/></body></html>'

    with pytest.raises(ValueError):
        filter_links(htmlstring, url=None, base_url=base_url)

    assert filter_links(htmlstring, url=base_url) == (["https://example.org/page1"], [])

    # link filtering with relative URLs
    url = "https://example.org/page1.html"
    htmlstring = '<html><body><a href="/subpage1"/><a href="/subpage1/"/><a href="https://test.org/page1"/></body></html>'
    assert filter_links(htmlstring, url=url) == (["https://example.org/subpage1"], [])


def test_filter_links_with_rules():
    "filter_links drops robots.txt-disallowed links and honors the external flag."
    rules = RobotFileParser()
    rules.parse(["User-agent: *", "Disallow: /private/"])
    htmlstring = (
        "<html><body>"
        '<a href="https://example.org/public/page">pub</a>'
        '<a href="https://example.org/private/secret">priv</a>'
        "</body></html>"
    )
    links, _ = filter_links(htmlstring, url="https://example.org", rules=rules)
    assert links == ["https://example.org/public/page"]

    # external flag: keep only links leading to another host (or only internal ones)
    htmlstring = (
        '<html><body><a href="https://other.org/x">ext</a>'
        '<a href="https://example.org/y">int</a></body></html>'
    )
    external, _ = filter_links(htmlstring, url="https://example.org", external=True)
    internal, _ = filter_links(htmlstring, url="https://example.org", external=False)
    assert external == ["https://other.org/x"]
    assert internal == ["https://example.org/y"]


def test_examples():
    """test README examples"""
    assert check_url("https://github.com/adbar/courlan") == (
        "https://github.com/adbar/courlan",
        "github.com",
    )
    assert check_url("http://666.0.0.1/") is None
    assert check_url("http://test.net/foo.html?utm_source=twitter#gclid=123") == (
        "http://test.net/foo.html",
        "test.net",
    )
    assert check_url(
        "https://httpbun.org/redirect-to?url=http%3A%2F%2Fexample.org", strict=True
    ) == ("https://httpbun.org/redirect-to", "httpbun.org")
    # non-default port for the scheme is preserved (:80 on https)
    assert clean_url("HTTPS://WWW.DWDS.DE:80/") == "https://www.dwds.de:80"
    assert validate_url("http://1234") == (False, None)
    assert validate_url("http://www.example.org/")[0] is True
    assert (
        normalize_url(
            "http://test.net/foo.html?utm_source=twitter&post=abc&page=2#fragment",
            strict=True,
        )
        == "http://test.net/foo.html?page=2&post=abc"
    )


def test_meta():
    get_registrable_domain("www.example.com")
    _parse("https://example.net/123/abc")

    # urlsplit is only an lru_cache wrapper on some Python versions
    has_urlsplit_cache = hasattr(urlsplit, "cache_info")
    assert get_registrable_domain.cache_info().currsize > 0
    assert _host_parts.cache_info().currsize > 0
    if has_urlsplit_cache:
        assert urlsplit.cache_info().currsize > 0  # type: ignore[attr-defined]

    clear_caches()

    assert get_registrable_domain.cache_info().currsize == 0
    assert _host_parts.cache_info().currsize == 0
    if has_urlsplit_cache:
        assert urlsplit.cache_info().currsize == 0  # type: ignore[attr-defined]


def test_extract_links_host_forms():
    "Internal links are found whatever the form of the page host."
    html = '<a href="/artikel-1">a</a><a href="https://münchen.de/b">b</a>'
    for page in (
        "https://xn--mnchen-3ya.de/",
        "https://münchen.de/",
        "https://MÜNCHEN.de/",
    ):
        assert extract_links(html, page, strict=False) == [
            "https://münchen.de/artikel-1",
            "https://münchen.de/b",
        ]
        assert extract_links(html, page, external_bool=True, strict=False) == []
    # IDNA2008 deviation characters decode to one form
    html = '<a href="https://faß.de/x">x</a><a href="https://xn--fa-hia.de/y">y</a>'
    assert extract_links(html, "https://xn--fa-hia.de/", external_bool=False) == [
        "https://faß.de/x",
        "https://faß.de/y",
    ]
    # userinfo of the page URL is not copied into the links
    assert extract_links(
        '<a href="/rel">x</a>', "https://u:p@ex.org/page", strict=False
    ) == ["https://ex.org/rel"]
    # external links only
    html = '<a href="https://other.org/a">a</a><a href="/b">b</a>'
    assert extract_links(html, "https://ex.org/", external_bool=True, strict=False) == [
        "https://other.org/a"
    ]
    # bare public suffix hosts are distinct sites
    html = '<a href="https://gov.au/a">a</a><a href="/b">b</a>'
    assert extract_links(html, "https://gov.uk/", strict=False) == ["https://gov.uk/b"]
    assert extract_links(html, "https://gov.uk/", external_bool=True, strict=False) == [
        "https://gov.au/a"
    ]


def test_extract_links_first_variant():
    "The first variant of a link in the document wins."
    html = (
        '<a href="https://ex.org/a">1</a><a href="http://ex.org/a">2</a>'
        '<a href="https://ex.org/b/">3</a><a href="https://ex.org/b">4</a>'
    )
    assert extract_links(html, "https://ex.org/", strict=False) == [
        "https://ex.org/a",
        "https://ex.org/b/",
    ]


def test_link_order_hash_seed():
    "Links come in document order whatever the hash seed."
    code = (
        "import sys\n"
        "from courlan import filter_links\n"
        "print(filter_links(sys.argv[1], 'https://news.example.org', strict=True, lang='en'))"
    )
    html = (
        '<a href="/2026/11/new-climate-report.html">a</a>'
        '<a href="/story.html">b</a><a href="/tag/climate/page/7/">c</a>'
    )
    expected = str(
        filter_links(html, "https://news.example.org", strict=True, lang="en")
    )
    for seed in ("0", "1"):
        result = subprocess.run(
            [sys.executable, "-c", code, html],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == expected


def test_check_url_host_forms():
    "Ports and IPv6 addresses have one form, userinfo is dropped."
    assert check_url("https://ex.org:08080/a") == ("https://ex.org:8080/a", "ex.org")
    assert check_url("https://ex.org:/a") == ("https://ex.org/a", "ex.org")
    assert check_url("https://ex.org:0443/a") == ("https://ex.org/a", "ex.org")
    assert check_url("https://[2001:db8:0:0::1]/a") == (
        "https://[2001:db8::1]/a",
        "2001:db8::1",
    )
    assert check_url("https://user:secret@ex.org/a") == ("https://ex.org/a", "ex.org")
    # userinfo stays out of the host cache
    _host_parts.cache_clear()
    check_url("https://user:secret@ex.org/a")
    check_url("https://ex.org/b")
    assert _host_parts.cache_info().currsize == 1
    assert check_url("https://allegro.pl/oferta") == (
        "https://allegro.pl/oferta",
        "allegro.pl",
    )
    assert check_url("https://163.com/news/a.html") == (
        "https://163.com/news/a.html",
        "163.com",
    )
    assert check_url("http://index.html/x") is None
    # RTL labels ending in a digit fail the IDNA2003 bidi rule, kept in punycode
    assert check_url("https://xn--1-9hcuf1d.com/page") == (
        "https://xn--1-9hcuf1d.com/page",
        "xn--1-9hcuf1d.com",
    )
    # the strict blacklist applies to the label and to the domain
    assert check_url("https://www.facebook.com/x", strict=True) is None
    assert check_url("https://www.facebook.com/x") is not None
