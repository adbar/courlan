"""
Unit tests for the courlan package: check_url, link extraction and network.
"""

from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import pytest

from courlan import (
    check_url,
    clean_url,
    extract_links,
    normalize_url,
    validate_url,
)
from courlan.core import filter_links
from courlan.hosts import get_registrable_domain
from courlan.langcodes import langcodes_score
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
    assert check_url("http://example.com/de/test.html", language="de") is not None
    assert check_url("http://example.com/en/test.html", language="de") is None
    assert check_url("http://example.com/en/test.html", language=None) is not None
    assert check_url("http://example.com/en/test.html", language="en") is not None
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
        "http://[2001:0db8:85a3:0000:0000:8a2e:0370:7334]",
        "2001:db8:85a3::8a2e:370:7334",
    )
    assert check_url("http://[2001:db8::1]/page") == (
        "http://[2001:db8::1]/page",
        "2001:db8::1",
    )
    assert check_url("http://1:2:3:4:5:6:7:8:9") is None
    # bare suffix has no registrable domain, though domain_filter alone accepts it
    assert check_url("https://a.ck/page") is None
    assert check_url("https://co.uk/page") is None
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
    ]
    configs = (
        {"strict": False},
        {"strict": True},
        {"strict": False, "language": "de"},
        {"strict": True, "language": "en"},
        {"strict": True, "trailing_slash": False},
    )
    for url in urls:
        for config in configs:
            first = check_url(url, **config)
            if first:
                assert check_url(first[0], **config) == first, (url, config)


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

    def _fake_head(status, location):
        resp = MagicMock()
        resp.status = status
        resp.geturl.return_value = location
        return resp

    with patch("courlan.network.HTTP_POOL.request") as mock_request:
        # acceptable status code: resolve to the final URL
        mock_request.return_value = _fake_head(200, "http://example.org")
        assert check_url(
            "https://httpbun.org/redirect-to?url=http%3A%2F%2Fexample.org",
            with_redirects=True,
        ) == ("http://example.org", "example.org")
        # unacceptable status code: rejected
        mock_request.return_value = _fake_head(404, "https://httpbun.org/status/404")
        assert check_url("https://httpbun.org/status/404", with_redirects=True) is None
        # transport failure: redirection_test raises ValueError, check_url returns None
        mock_request.side_effect = Exception("unreachable")
        assert check_url("https://www.ht.or", with_redirects=True) is None
        # geturl() returns None in urllib3 2.x
        mock_request.side_effect = None
        mock_request.return_value = _fake_head(200, None)
        assert check_url("http://example.org/page", with_redirects=True) == (
            "http://example.org/page",
            "example.org",
        )


def test_redirection(httpserver):
    "Test redirection_test against a real local HTTP server (no external network)."
    httpserver.expect_request("/redirect", method="HEAD").respond_with_data(
        "", status=302, headers={"Location": httpserver.url_for("/final")}
    )
    httpserver.expect_request("/final", method="HEAD").respond_with_data("", status=200)
    httpserver.expect_request("/missing", method="HEAD").respond_with_data(
        "", status=404
    )

    # the redirect is actually followed by urllib3 to the final URL
    assert redirection_test(httpserver.url_for("/redirect")) == httpserver.url_for(
        "/final"
    )
    # an unacceptable status code raises
    with pytest.raises(ValueError):
        redirection_test(httpserver.url_for("/missing"))


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
    assert extract_links(pagecontent, "https://example.org", False) == {
        "https://example.org"
    }
    assert extract_links(pagecontent, "https://example.org", no_filter=True) == {
        "https://example.org"
    }
    pagecontent = '<html><a href="">x</a></html>'
    assert extract_links(pagecontent, "https://example.org", False) == {
        "https://example.org"
    }
    assert extract_links(pagecontent, "https://example.org", no_filter=True) == {
        "https://example.org"
    }
    # link known under another form
    pagecontent = '<html><a href="https://test.org/example"/><a href="https://test.org/example/&"/></html>'
    assert extract_links(pagecontent, "https://test.org", False) == {
        "https://test.org/example"
    }
    # nofollow
    pagecontent = '<html><a href="https://test.com/example" rel="nofollow ugc"/></html>'
    assert not extract_links(pagecontent, "https://test.com/", False)
    pagecontent = '<html><a href="https://test.com/rel/nofollow-guide"/></html>'
    assert extract_links(pagecontent, "https://test.com/", False) == {
        "https://test.com/rel/nofollow-guide"
    }
    # language
    example = {"https://test.com/example"}
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
    pagecontent = '<html><a hreflang="de-DE" href="https://test.com/example"/><a href="https://test.com/example2"/><a href="https://test.com/example2 ADDITIONAL"/></html>'
    links = extract_links(pagecontent, "https://test.com/", external_bool=False)
    assert sorted(links) == ["https://test.com/example", "https://test.com/example2"]
    assert extract_links(pagecontent, "https://test.com/", language="de") == set(links)
    pagecontent = '<html><a hreflang="de-DE" href="https://test.com/example"/><a href="https://test.com/page/2"/></html>'
    assert extract_links(pagecontent, "https://test.com/", with_nav=False) == example
    assert extract_links(pagecontent, "https://test.com/", with_nav=True) == {
        "https://test.com/example",
        "https://test.com/page/2",
    }
    # filtered, invalid or duplicate links must not stop extraction of later ones
    pagecontent = '<html><a href="https://test.com/skip" rel="nofollow"/><a href="https://test.com/keep"/></html>'
    assert extract_links(pagecontent, "https://test.com/") == {"https://test.com/keep"}
    pagecontent = '<html><a href="http://t.g/x"/><a href="https://test.com/ok"/></html>'
    assert extract_links(pagecontent, "https://test.com/") == {"https://test.com/ok"}
    pagecontent = '<html><a href="https://test.com/a"/><a href="https://test.com/a"/><a href="https://test.com/b"/></html>'
    assert extract_links(pagecontent, "https://test.com/") == {
        "https://test.com/a",
        "https://test.com/b",
    }


def test_extraction_navigation():
    "Test link extraction for navigation and CMS edge cases."
    pagecontent = "<html><head><title>Links</title></head><body><a href='/links/2/0'>0</a> <a href='/links/2/1'>1</a> </body></html>"
    links = extract_links(
        pagecontent, "https://httpbun.org", external_bool=False, with_nav=True
    )
    assert sorted(links) == [
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
    assert sorted(links) == [
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
        == set()
    )
    links = extract_links(
        pagecontent,
        "https://example.org",
        external_bool=False,
        strict=True,
        with_nav=True,
        trailing_slash=True,
    )
    assert sorted(links) == [
        "https://example.org/page/",
        "https://example.org/page/10",
    ]
    links = extract_links(
        pagecontent,
        "https://example.org",
        external_bool=False,
        strict=True,
        trailing_slash=False,
        with_nav=True,
    )
    assert sorted(links) == [
        "https://example.org/page",  # parameter stripped by strict filtering
        "https://example.org/page/10",
    ]
    links = extract_links(
        pagecontent,
        "https://example.org",
        external_bool=False,
        strict=False,
        with_nav=True,
    )
    assert sorted(links) == [
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
    assert extract_links(pagecontent, "https://test.com/", external_bool=False) == {
        "https://test.com/link"
    }
    assert extract_links(pagecontent, "https://test.com/", external_bool=True) == set()
    pagecontent = "<html><a href=/link attribute=value>Link</a></html>"
    assert extract_links(pagecontent, "https://test.com/", external_bool=False) == {
        "https://test.com/link"
    }
    # external links with extension (here ".com")
    pagecontent = '<html><body><a href="https://knoema.com/o/data-engineer-india"/><a href="https://knoema.recruitee.com/"/></body></html>'
    assert extract_links(pagecontent, "https://knoema.com/", external_bool=False) == {
        "https://knoema.com/o/data-engineer-india"
    }
    assert extract_links(pagecontent, "https://knoema.com/", external_bool=True) == {
        "https://knoema.recruitee.com"
    }
    # without url, external_bool must not filter (no reference to compare)
    pagecontent = '<html><a href="https://example.com/page"/><a href="https://other.org/post"/></html>'
    expected = {"https://example.com/page", "https://other.org/post"}
    assert extract_links(pagecontent) == expected
    assert extract_links(pagecontent, external_bool=True) == expected
    # return all links without filters
    pagecontent = '<html><a hreflang="de-DE" href="https://test.com/example"/><a href="/page/2"/><a href="https://example.com/gallery/"/></html>'
    result = extract_links(
        pagecontent, "https://test.com", external_bool=True, no_filter=True
    )
    assert sorted(result) == [
        "https://example.com/gallery/",
        "https://test.com/example",
        "https://test.com/page/2",
    ]


def test_filter_links():
    base_url = "https://example.org"
    htmlstring = '<html><body><a href="https://example.org/page1"/><a href="https://example.org/page1/"/><a href="https://test.org/page1"/></body></html>'

    with pytest.raises(ValueError):
        filter_links(htmlstring, url=None, base_url=base_url)

    links, links_priority = filter_links(htmlstring, url=base_url)
    assert len(links) == 1 and not links_priority

    # link filtering with relative URLs
    url = "https://example.org/page1.html"
    htmlstring = '<html><body><a href="/subpage1"/><a href="/subpage1/"/><a href="https://test.org/page1"/></body></html>'
    links, links_priority = filter_links(htmlstring, url=url)
    assert len(links) == 1 and not links_priority


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
    _ = langcodes_score("en", "en_HK")
    _ = get_registrable_domain("www.example.com")
    _ = _parse("https://example.net/123/abc")

    # urlsplit is only an lru_cache wrapper on some Python versions
    has_urlsplit_cache = hasattr(urlsplit, "cache_info")
    assert langcodes_score.cache_info().currsize > 0
    assert get_registrable_domain.cache_info().currsize > 0
    if has_urlsplit_cache:
        assert urlsplit.cache_info().currsize > 0  # type: ignore[attr-defined]

    clear_caches()

    assert langcodes_score.cache_info().currsize == 0
    assert get_registrable_domain.cache_info().currsize == 0
    if has_urlsplit_cache:
        assert urlsplit.cache_info().currsize == 0  # type: ignore[attr-defined]
