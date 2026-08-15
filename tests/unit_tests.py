"""
Unit tests for the courlan package.
"""

import io
import logging
import os
import subprocess
import sys
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch
from urllib.parse import SplitResult, urlsplit

import pytest

from courlan import (
    check_url,
    clean_url,
    cli,
    extract_domain,
    extract_links,
    filter_urls,
    fix_relative_urls,
    get_base_url,
    get_host_and_path,
    get_hostinfo,
    is_external,
    is_navigation_page,
    is_not_crawlable,
    is_valid_url,
    lang_filter,
    normalize_url,
    sample_urls,
    scrub_url,
    validate_url,
)
from courlan.clean import clean_query, normalize_and_split, normalize_path
from courlan.core import filter_links
from courlan.filters import (
    basic_filter,
    domain_filter,
    extension_filter,
    path_filter,
    type_filter,
)
from courlan.hosts import (
    EXCEPTIONS,
    MULTI_PART_SUFFIXES,
    WILDCARD_BASES,
    _idna_encode,
    _idna_label,
    get_registrable_domain,
)
from courlan.langcodes import langcodes_score
from courlan.meta import clear_caches
from courlan.network import redirection_test
from courlan.urlutils import _parse, _strip_trailing_dot, is_known_link

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
RESOURCES_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data")


def test_baseurls():
    assert get_base_url("https://example.org/") == "https://example.org"
    assert (
        get_base_url("https://example.org/test.html?q=test#frag")
        == "https://example.org"
    )
    assert get_base_url("example.org") == ""


def test_malformed_url_degrades():
    # A malformed URL (bad IPv6 literal) made urlsplit raise a raw ValueError that
    # leaked out of get_base_url/get_hostinfo; it now degrades like a hostless URL.
    assert get_base_url("HTTP://[::1]&") == ""
    assert get_hostinfo("HTTP://[::1]&") == (None, "")
    # get_host_and_path still raises its own documented incomplete-URL error.
    with pytest.raises(ValueError, match="incomplete URL"):
        get_host_and_path("HTTP://[::1]&")
    # valid and hostless URLs are unaffected.
    assert get_base_url("https://example.org/") == "https://example.org"
    assert get_hostinfo("https://example.org/path") == (
        "example.org",
        "https://example.org",
    )


def test_fix_relative():
    assert (
        fix_relative_urls("https://example.org", "page.html")
        == "https://example.org/page.html"
    )
    assert (
        fix_relative_urls("http://example.org", "//example.org/page.html")
        == "http://example.org/page.html"
    )
    assert (
        fix_relative_urls("https://example.org", "./page.html")
        == "https://example.org/page.html"
    )
    assert (
        fix_relative_urls("https://example.org", "/page.html")
        == "https://example.org/page.html"
    )
    # fixing partial URLs
    assert (
        fix_relative_urls("https://example.org", "https://example.org/test.html")
        == "https://example.org/test.html"
    )
    assert (
        fix_relative_urls("https://example.org", "/test.html")
        == "https://example.org/test.html"
    )
    assert (
        fix_relative_urls("https://example.org", "//example.org/test.html")
        == "https://example.org/test.html"
    )
    assert (
        fix_relative_urls("http://example.org", "//example.org/test.html")
        == "http://example.org/test.html"
    )
    assert (
        fix_relative_urls("https://example.org", "test.html")
        == "https://example.org/test.html"
    )
    assert (
        fix_relative_urls("https://example.org", "../../test.html")
        == "https://example.org/test.html"
    )
    # sub-directories
    assert (
        fix_relative_urls("https://www.example.org/dir/subdir/file.html", "/absolute")
        == "https://www.example.org/absolute"
    )
    assert (
        fix_relative_urls("https://www.example.org/dir/subdir/file.html", "relative")
        == "https://www.example.org/dir/subdir/relative"
    )
    assert (
        fix_relative_urls("https://www.example.org/dir/subdir/", "relative")
        == "https://www.example.org/dir/subdir/relative"
    )
    assert (
        fix_relative_urls("https://www.example.org/dir/subdir", "relative")
        == "https://www.example.org/dir/relative"
    )
    # non-relative URLs
    assert (
        fix_relative_urls("https://example.org", "https://www.eff.org")
        == "https://www.eff.org"
    )
    assert (
        fix_relative_urls("https://example.org", "//www.eff.org")
        == "https://www.eff.org"
    )
    assert (
        fix_relative_urls("http://example.org", "//www.eff.org") == "http://www.eff.org"
    )
    assert (
        fix_relative_urls("http://example.org", "https://www.eff.org")
        == "https://www.eff.org"
    )
    # looks like an absolute URL but is actually a valid relative URL
    assert (
        fix_relative_urls("https://example.org", "www.eff.org")
        == "https://example.org/www.eff.org"
    )
    # misc
    assert (
        fix_relative_urls("https://www.example.org/dir/subdir/file.html", "./this:that")
        == "https://www.example.org/dir/subdir/this:that"
    )
    assert (
        fix_relative_urls(
            "https://www.example.org/test.html?q=test#frag", "foo.html?q=bar#baz"
        )
        == "https://www.example.org/foo.html?q=bar#baz"
    )
    assert fix_relative_urls("https://www.example.org", "{privacy}") == "{privacy}"
    # a malformed netloc used to abort extract_links, discarding the whole page
    assert fix_relative_urls("https://example.org", "//[zz]/x") == "//[zz]/x"
    assert fix_relative_urls("https://[zz]", "/page.html") == "/page.html"
    assert extract_links(
        '<a href="//[zz]/x">a</a><a href="/ok">b</a>', "https://example.org"
    ) == {"https://example.org/ok"}


def test_scrub():
    # clean: scrub + normalize
    assert clean_url(5) is None
    assert clean_url("ø\xaa") == "%C3%B8%C2%AA"
    assert clean_url("https://example.org/?p=100") == "https://example.org/?p=100"
    # query keys that are HTML entity names must survive intact
    assert (
        clean_url("https://example.org/a?b=1&param=2")
        == "https://example.org/a?b=1&param=2"
    )
    assert clean_url("https://example.org/ab'c") == "https://example.org/ab%27c"
    assert clean_url('https://example.org/abc"') == "https://example.org/abc"
    assert clean_url("https://example.org/abc<") == "https://example.org/abc"
    assert clean_url("https://example.org/\t?p=100") == "https://example.org/?p=100"
    assert (
        clean_url("https://example.org:443/file.html?p=100&abc=1#frag")
        == "https://example.org/file.html?abc=1&p=100#frag"
    )
    # clean_url is idempotent, including when all query parameters are stripped
    for url in (
        "http://test.org/?s_cid=123&clickid=1",
        "http://test.org/?utm_source=&utm_medium=",
        "http://test.org/#partnerid=123",
    ):
        cleaned = clean_url(url)
        assert cleaned == "http://test.org"
        assert clean_url(cleaned) == cleaned
    # a surviving (non-tracker) query still keeps the root slash
    assert clean_url("http://test.org/?p=1") == "http://test.org/?p=1"
    # trailing slashes are stripped
    assert clean_url("https://example.org/path/") == "https://example.org/path"
    assert clean_url("https://example.org/path") == "https://example.org/path"
    # scrub
    assert scrub_url("  https://www.dwds.de") == "https://www.dwds.de"
    assert scrub_url("<![CDATA[https://www.dwds.de]]>") == "https://www.dwds.de"
    assert (
        scrub_url("https://www.dwds.de/test?param=test&amp;other=test")
        == "https://www.dwds.de/test?param=test&other=test"
    )
    assert (
        scrub_url("https://www.dwds.de/garbledhttps://www.dwds.de/")
        == "https://www.dwds.de/garbled"
    )
    assert scrub_url("https://g__https://www.dwds.de/") == "https://www.dwds.de"
    # double URL where neither candidate is valid: left untouched
    assert scrub_url("https://g__https://h__") == "https://g__https://h__"
    # exception for archive URLs
    assert (
        scrub_url("https://web.archive.org/web/20131021165347/https://www.imdb.com/")
        == "https://web.archive.org/web/20131021165347/https://www.imdb.com"
    )
    # social sharing
    assert (
        scrub_url(
            "https://twitter.com/share?&text=Le%20sabre%20de%20bambou%20%232&via=NouvellesJapon&url=https://nouvellesdujapon.com/le-sabre-de-bambou-2"
        )
        == "https://nouvellesdujapon.com/le-sabre-de-bambou-2"
    )
    assert (
        scrub_url(
            "https://www.facebook.com/sharer.php?u=https://nouvellesdujapon.com/le-sabre-de-bambou-2"
        )
        == "https://nouvellesdujapon.com/le-sabre-de-bambou-2"
    )
    # end of URL
    assert scrub_url("https://www.test.com/&") == "https://www.test.com"
    # white space
    assert scrub_url("\x19https://www.test.com/\x06") == "https://www.test.com"
    # markup
    assert scrub_url("https://www.test.com/</a>") == "https://www.test.com"
    assert scrub_url("https://www.test.com/1</div>") == "https://www.test.com/1"
    assert scrub_url("https://www.test.com/{user_name}") == "https://www.test.com"
    # garbled URLs e.g. due to quotes
    assert (
        scrub_url('https://www.test.com/"' + "<p></p>" * 100) == "https://www.test.com"
    )
    assert scrub_url('https://www.test.com/"' * 50) == "https://www.test.com"
    # simply too long, left untouched
    my_url = "https://www.test.com/" + "abcdefg" * 100
    assert scrub_url(my_url) == my_url


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/test.js", False),
        ("/GirlInfo.aspx", True),
        ("/de/vermoegensrecht.amp", True),
        ("/test.shtml", True),
        ("/ADC/Art.nsf/O/8EWETN", True),
        ("/ADC/Art.nsf", False),  # bare .nsf (query stripped by urlsplit)
        ("/test.xhtml", True),
        ("/test.php5", True),
        ("/test.php6", True),
        ("/photo.JPG", False),  # uppercase treated like lowercase
        ("/page.HTML", True),
        ("/index.PHP", True),
    ],
)
def test_extension_filter(path, expected):
    assert extension_filter(path) is expected


def test_spam_filter():
    assert (
        type_filter("http://www.example.org/livecams/test.html", strict=False) is True
    )
    assert (
        type_filter("http://www.example.org/livecams/test.html", strict=True) is False
    )
    assert type_filter("http://www.example.org/test.html") is True


def test_type_filter():
    assert type_filter("http://www.example.org/feed") is False
    # the feed check looks at the path: trailing slashes, query and fragment
    # do not change the verdict, but a feed-like param is not a feed
    assert type_filter("http://www.example.org/feed/") is False
    assert type_filter("http://www.example.org/feed//") is False
    assert type_filter("http://www.example.org/feed/#f") is False
    assert type_filter("http://www.example.org/feed?x=1") is False
    assert type_filter("http://www.example.org/rss/") is False
    assert type_filter("http://www.example.org/2011_archive.html/") is False
    assert type_filter("http://www.example.org/feeds/posts/default") is True
    assert type_filter("http://www.example.org/feed/x") is True
    assert type_filter("http://www.example.org/myfeed") is True
    assert type_filter("http://www.example.org/page?url=/feed") is True
    # wp
    assert type_filter("http://www.example.org/wp-admin/") is False
    assert type_filter("http://www.example.org/wp-includes/this") is False
    # straight category
    assert type_filter("http://www.example.org/category/123") is False
    assert type_filter("http://www.example.org/product-category/123") is False
    # post simply filed under a category
    assert type_filter("http://www.example.org/category/tropes/time-travel") is True
    assert (
        type_filter("http://www.example.org/test.xml?param=test", strict=True) is False
    )
    assert type_filter("http://www.example.org/test.asp") is True
    # -video- vs. /video/
    assert type_filter("http://my-livechat.com/") is True
    assert type_filter("http://my-livechat.com/", strict=True) is False
    assert type_filter("http://example.com/livechat/1", strict=True) is False
    assert type_filter("http://example.com/new-sexcam") is True
    assert type_filter("http://example.com/new-sexcam", strict=True) is False
    # tags
    assert type_filter("https://de.thecitizen.de/tag/anonymity/") is False
    assert type_filter("https://de.thecitizen.de/tags/anonymity/") is False
    # author
    assert type_filter("http://www.example.org/author/abcde") is False
    assert type_filter("http://www.example.org/autor/abcde/") is False
    # archives
    assert type_filter("http://www.example.org/2011/11/") is False
    assert type_filter("http://www.example.org/2011/") is False
    assert type_filter("http://www.example.org/2011_archive.html") is False
    assert type_filter("http://www.example.org/2020/02/06/1859/") is True
    # misc
    assert (
        type_filter("http://www.bmbwk.gv.at/forschung/fps/gsk/befragung.xml?style=text")
        is True
    )
    assert (
        type_filter(
            "http://www.aec.at/de/archives/prix_archive/prix_projekt.asp?iProjectID=11118"
        )
        is False
    )
    # nav
    assert type_filter("http://www.example.org/tag/abcde/", with_nav=False) is False
    assert type_filter("http://www.example.org/tag/abcde/", with_nav=True) is True
    assert type_filter("http://www.example.org/page/10/", with_nav=False) is False
    assert type_filter("http://www.example.org/page/10/", with_nav=True) is True
    # img
    assert type_filter("http://www.example.org/logo_800_web-jpg/", strict=True) is False
    assert (
        type_filter("http://www.example.org/img_2020-03-03_25/", strict=True) is False
    )


def test_path_filter():
    assert (
        check_url(
            "http://www.case-modder.de/index.php?sec=artikel&id=68&page=1", strict=True
        )
        is not None
    )
    assert path_filter("/index.php", "") is False
    assert check_url("http://www.case-modder.de/index.php", strict=True) is None
    assert path_filter("/default/", "") is False
    assert check_url("http://www.case-modder.de/default/", strict=True) is None
    assert path_filter("/contact/", "") is False
    assert path_filter("/Datenschutzerklaerung", "") is False
    # umlaut paths, raw and percent-quoted
    assert path_filter("/datenschutzerklärung", "") is False
    assert path_filter("/datenschutzerkl%C3%A4rung", "") is False
    assert check_url("http://example.org/datenschutzerklärung", strict=True) is None
    # assert path_filter("/", "") is False

    # in strict mode an index page must not be kept alive by a query that
    # normalization strips again: that returned a bare index URL which
    # check_url itself rejects, so the result was not idempotent
    for url in (
        "http://www.case-modder.de/index.php?utm_source=x",  # tracker
        "http://www.case-modder.de/index.php?sec=artikel",  # non-whitelisted key
        "http://www.case-modder.de/default/?ref=abc",
        "http://www.case-modder.de/home?foo=bar",
    ):
        assert check_url(url, strict=True) is None
    # an index page with a surviving (whitelisted) query is still kept, and the
    # canonical output is stable under a second pass
    for url in (
        "http://www.case-modder.de/index.php?id=68&page=1",
        "http://www.case-modder.de/index.php?p=2",
    ):
        checked = check_url(url, strict=True)
        assert checked is not None
        assert check_url(checked[0], strict=True) == checked
    # non-index pages are unaffected by query stripping
    assert check_url("http://www.case-modder.de/article.html?ref=x", strict=True) == (
        "http://www.case-modder.de/article.html",
        "case-modder.de",
    )
    # a whitelisted param survives while a co-occurring tracker is stripped, so
    # the index page is kept with only its meaningful query (also for &amp;)
    assert check_url(
        "http://www.case-modder.de/index.php?utm_source=x&id=68", strict=True
    ) == ("http://www.case-modder.de/index.php?id=68", "case-modder.de")
    assert check_url(
        "http://www.case-modder.de/index.php?utm_source=x&amp;id=68", strict=True
    ) == ("http://www.case-modder.de/index.php?id=68", "case-modder.de")
    # a language param matching the requested language keeps the index page,
    # while a mismatching one is filtered out
    assert (
        check_url(
            "http://www.case-modder.de/index.php?lang=en", strict=True, language="en"
        )
        is not None
    )
    assert (
        check_url(
            "http://www.case-modder.de/index.php?lang=fr", strict=True, language="en"
        )
        is None
    )
    # only strict mode is affected: non-strict still returns the bare index page
    assert check_url(
        "http://www.case-modder.de/index.php?utm_source=x", strict=False
    ) == ("http://www.case-modder.de/index.php", "case-modder.de")


_20MIN_FR = "https://www.20min.ch/fr/story/des-millions-pour-produire-de-l-energie-renouvelable-467974085377"
_TU_BERLIN = "http://ig.cs.tu-berlin.de/oldstatic/w2000/ir1/aufgabe2/ir1-auf2-gr16.html"
_MUSCLEFOOD = "http://de.musclefood.com/neu/neue-nahrungsergaenzungsmittel.html"


@pytest.mark.parametrize(
    "url, lang, kwargs, expected",
    [
        ("http://test.com/az", "de", {"trailing_slash": False}, False),
        ("http://test.com/az/", "de", {}, False),
        ("http://test.com/de", "de", {"trailing_slash": False}, True),
        ("http://test.com/de/", "de", {}, True),
        (_20MIN_FR, None, {}, True),
        (_20MIN_FR, "de", {}, False),
        (_20MIN_FR, "fr", {}, True),
        (_20MIN_FR, "en", {}, False),
        (_20MIN_FR, "es", {}, False),
        ("https://www.sitemaps.org/en_GB/protocol.html", "en", {}, True),
        ("https://www.sitemaps.org/en_GB/protocol.html", "de", {}, False),
        ("https://en.wikipedia.org/", "de", {"strict": True}, False),
        ("https://en.wikipedia.org/", "de", {"strict": False}, True),
        ("https://de.wikipedia.org/", "de", {"strict": True}, True),
        (_MUSCLEFOOD, "de", {"strict": True}, True),
        (_MUSCLEFOOD, "fr", {"strict": True}, False),
        ("http://ch.postleitzahl.org/sankt_gallen/liste-T.html", "fr", {}, True),
        ("http://ch.postleitzahl.org/sankt_gallen/liste-T.html", "de", {}, True),
        # disturbing path sub-elements
        (
            "http://www.uni-rostock.de/fakult/philfak/fkw/iph/thies/mythos.html",
            "de",
            {},
            True,
        ),
        ("http://stifter.literature.at/witiko/htm/h15-22b.html", "de", {}, True),
        ("http://stifter.literature.at/doc/witiko/h15-22b.html", "de", {}, True),
        ("http://stifter.literature.at/nl/witiko/h15-22b.html", "de", {}, False),
        ("http://stifter.literature.at/de_DE/witiko/h15-22b.html", "de", {}, True),
        ("http://stifter.literature.at/en_US/witiko/h15-22b.html", "de", {}, False),
        (
            "http://www.stiftung.koerber.de/bg/recherche/de/beitrag.php?id=15132&refer=",
            "de",
            {},
            True,
        ),
        ("http://www.solingen-internet.de/si-hgw/eiferer.htm", "de", {}, True),
        (_TU_BERLIN, "de", {"strict": True}, True),
        (_TU_BERLIN, "de", {"strict": False}, True),
        ("http://bz.berlin1.de/kino/050513/fans.html", "de", {"strict": False}, True),
        ("http://bz.berlin1.de/kino/050513/fans.html", "de", {"strict": True}, False),
        # both path segments differ from target
        ("https://x.com/fr/x/de/", "en", {}, False),
        # invalid territory: de segment wins
        ("https://x.com/en_XY/x/de/", "en", {}, False),
        # >2 candidates: unreliable, score stays 0
        ("https://x.com/en/x/de/x/fr/", "en", {}, True),
        # adjacent segments (regression: consuming regex)
        ("https://x.com/de/en/", "en", {}, True),
        ("https://x.com/de/fr/", "en", {}, False),
        # /ch/ is not a language code
        ("http://www.verfassungen.de/ch/basel/verf03.htm", "de", {}, True),
        # multiple path occurrences / strict host+path
        ("http://example.com/en/page/en-US/test", "en", {"strict": True}, True),
        ("http://example.com/en/page/de/test", "en", {"strict": True}, True),
        ("http://de.example.com/en/page", "en", {"strict": True}, True),
        ("http://fr.example.com/de/page", "en", {"strict": True}, False),
        ("http://en.example.com/de/page", "en", {"strict": True}, True),
    ],
)
def test_lang_filter(url, lang, kwargs, expected):
    assert lang_filter(url, lang, **kwargs) is expected


def test_langcodes_score():
    assert langcodes_score("en", "en_HK") == 1
    assert langcodes_score("en", "en-HK") == 1
    assert langcodes_score("en", "de_DE") == -1
    assert langcodes_score("en", "de-DE") == -1
    assert langcodes_score("en", "en_XY") == 0  # invalid territory
    assert langcodes_score("en", "en-XY") == 0
    assert langcodes_score("en", "xx") == 0  # invalid language
    assert langcodes_score("en", "xx_US") == 0
    # major territories must be recognized (regression: the biased en_XX-generated
    # ISO_TERRS was missing CN/JP/BR/… so these scored 0 instead of ±1)
    assert langcodes_score("pt", "pt-BR") == 1
    assert langcodes_score("zh", "zh-CN") == 1
    assert langcodes_score("en", "zh-CN") == -1


def test_navigation():
    assert is_navigation_page("https://test.org/") is False
    assert is_navigation_page("https://test.org/page/1") is True
    assert is_navigation_page("https://test.org/?p=11") is True
    assert is_not_crawlable("https://test.org/login") is True
    assert is_not_crawlable("https://test.org/login/") is True
    assert is_not_crawlable("https://test.org/login.php") is True
    assert is_not_crawlable("https://test.org/page") is False


def test_validate():
    assert validate_url("http://www.test[.org/test")[0] is False
    # assert validate_url('http://www.test.org:7ERT/test')[0] is False
    assert validate_url("ntp://www.test.org/test")[0] is False
    assert validate_url("ftps://www.test.org/test")[0] is False
    assert validate_url("http://t.g/test")[0] is False
    assert validate_url("http://test.org/test")[0] is True
    # assert validate_url("http://sub.-mkyong.com/test")[0] is False

    assert not is_valid_url("http://www.test[.org/test")
    assert is_valid_url("http://test.org/test")
    # non-string input
    assert not is_valid_url(None)
    assert not is_valid_url(123)
    assert not is_valid_url(b"http://test.org/test")

    # verdict no longer flips on port/userinfo/case; short valid domains accepted
    assert is_valid_url("http://t.co/")
    assert is_valid_url("http://t.co:80/")
    assert is_valid_url("http://user@t.co/")
    assert is_valid_url("http://g.co/")
    assert not is_valid_url("http://WWW.a.b/")
    assert not is_valid_url("http://www.a.b/")
    # dotless/colonless and too-short hosts stay rejected
    assert not is_valid_url("http://1234")
    assert not is_valid_url("http://localhost/")
    assert not is_valid_url("http://a.b/")
    # userinfo must not make check_url reject an otherwise-valid host
    assert check_url("http://user@t.co/") is not None
    assert check_url("https://user:pass@example.com/path") is not None


def test_normalization():
    # canonical root form has no trailing slash
    assert normalize_url("HTTPS://WWW.DWDS.DE/") == "https://www.dwds.de"
    assert (
        normalize_url("http://test.net/foo.html#bar", strict=True)
        == "http://test.net/foo.html"
    )
    assert (
        normalize_url("http://test.net/foo.html#bar", strict=False)
        == "http://test.net/foo.html#bar"
    )
    assert (
        normalize_url("http://test.net/foo.html#:~:text=night-,vision")
        == "http://test.net/foo.html#:~:text=night-,vision"
    )
    assert (
        normalize_url("http://www.example.org:80/test.html")
        == "http://www.example.org/test.html"
    )
    assert (
        normalize_url("http://www.example.org:80?p=123")
        == "http://www.example.org/?p=123"
    )
    assert (
        normalize_url("https://hanxiao.io//404.html") == "https://hanxiao.io/404.html"
    )
    # leading /../ segments are removed
    assert (
        normalize_url("https://example.org/../path/page.html")
        == "https://example.org/path/page.html"
    )
    assert normalize_path("/../../a//b") == "/a/b"

    # the (url, base, path) split needs a host: without one urlunsplit drops the
    # "//" and slicing past the base would cut into the path
    assert normalize_and_split(
        urlsplit("https://ex.org/a?b=1#f"), False, None, True
    ) == (
        "https://ex.org/a?b=1#f",
        "https://ex.org",
        "/a?b=1#f",
    )
    with pytest.raises(ValueError, match="no host"):
        normalize_and_split(urlsplit("https:path"), False, None, True)

    # IPv6: default port stripped (was missed by the old \w-lookbehind regex)
    assert normalize_url("http://[::1]:80/") == "http://[::1]"
    assert normalize_url("https://[::1]:443/") == "https://[::1]"
    # non-default port preserved
    assert normalize_url("http://[::1]:8080/") == "http://[::1]:8080"

    # userinfo case is preserved (credentials are case-sensitive)
    assert (
        normalize_url("https://User:PassWord@Example.COM/Path")
        == "https://User:PassWord@example.com/Path"
    )
    # empty userinfo is dropped
    assert normalize_url("http://@example.com/x") == "http://example.com/x"
    # trailing FQDN dot is stripped from the host
    assert normalize_url("http://example.com./page") == "http://example.com/page"
    assert (
        normalize_url("http://example.com.:8080/page") == "http://example.com:8080/page"
    )

    # punycode
    assert normalize_url("http://xn--Mnchen-3ya.de") == "http://münchen.de"
    assert normalize_url("http://Mnchen-3ya.de") == "http://mnchen-3ya.de"
    assert normalize_url("http://xn--München.de") == "http://xn--münchen.de"
    # punycode with non-default port
    assert normalize_url("http://xn--n3h:8080/") == "http://☃:8080"

    # account for particular characters
    assert (
        normalize_url(
            "https://www.deutschlandfunknova.de/beitrag/nord--und-s%C3%BCdgaza-israels-armee-verk%C3%BCndet-teilung-des-gazastreifens"
        )
        == "https://www.deutschlandfunknova.de/beitrag/nord--und-s%C3%BCdgaza-israels-armee-verk%C3%BCndet-teilung-des-gazastreifens"
    )
    assert (
        normalize_url("https://taz.de/Zukunft-des-49-Euro-Tickets/!5968518/")
        == "https://taz.de/Zukunft-des-49-Euro-Tickets/!5968518/"
    )

    # trackers
    assert normalize_url("http://test.org/?s_cid=123&clickid=1") == "http://test.org"
    assert normalize_url("http://test.org/?aftr_source=0") == "http://test.org"
    assert normalize_url("http://test.org/?fb_ref=0") == "http://test.org"
    assert normalize_url("http://test.org/?this_affiliate=0") == "http://test.org"
    assert (
        normalize_url("http://test.org/?utm_source=rss&utm_medium=rss")
        == "http://test.org"
    )
    assert (
        normalize_url("http://test.org/?utm_source=rss&#038;utm_medium=rss")
        == "http://test.org"
    )
    # numeric ampersand entity variants: all must decode to &
    assert normalize_url("http://test.org/?a=1&#38;b=2") == "http://test.org/?a=1&b=2"
    assert normalize_url("http://test.org/?a=1&#x26;b=2") == "http://test.org/?a=1&b=2"
    assert normalize_url("http://test.org/?a=1&#0038;b=2") == "http://test.org/?a=1&b=2"
    assert normalize_url("http://test.org/?a=1&#X26;b=2") == "http://test.org/?a=1&b=2"
    assert normalize_url("http://test.org/#partnerid=123") == "http://test.org"
    assert (
        normalize_url(
            "http://test.org/#mtm_campaign=documentation&mtm_keyword=demo&catpage=3"
        )
        == "http://test.org/#catpage=3"
    )
    assert normalize_url("http://test.org/#page2") == "http://test.org/#page2"


def test_qelems():
    assert (
        normalize_url("http://test.net/foo.html?utm_source=twitter")
        == "http://test.net/foo.html"
    )
    assert (
        normalize_url("http://test.net/foo.html?testid=1")
        == "http://test.net/foo.html?testid=1"
    )
    assert (
        normalize_url("http://test.net/foo.html?testid=1", strict=True)
        == "http://test.net/foo.html"
    )
    assert (
        normalize_url("http://test.net/foo.html?testid=1&post=abc&page=2")
        == "http://test.net/foo.html?page=2&post=abc&testid=1"
    )
    assert (
        normalize_url("http://test.net/foo.html?testid=1&post=abc&page=2", strict=True)
        == "http://test.net/foo.html?page=2&post=abc"
    )
    assert (
        normalize_url("http://test.net/foo.html?page=2&itemid=10&lang=en")
        == "http://test.net/foo.html?itemid=10&lang=en&page=2"
    )
    with pytest.raises(ValueError):
        normalize_url("http://test.net/foo.html?page=2&lang=en", language="de")
    with pytest.raises(ValueError):
        normalize_url(
            "http://www.evolanguage.de/index.php?page=deutschkurse_fuer_aerzte&amp;language=ES",
            language="de",
        )


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
    assert (
        check_url("http://example.com/index.html#term", strict=False)[0]
        == "http://example.com/index.html#term"
    )
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
    # assert check_url('http://www.immobilienscout24.de/de/ueberuns/presseservice/pressestimmen/2_halbjahr_2000.jsp;jsessionid=287EC625A45BD5A243352DD8C86D25CC.worker2', language='de', strict=True) is not None


def test_urlcheck_domain():
    "Test domain and host name validation through check_url."
    assert check_url("http://-100x100.webp") is None
    assert check_url("http://0.gravata.html") is None
    assert check_url("http://https:") is None
    assert check_url("http://127.0.0.1") is not None
    assert check_url("http://111.111.111.111") is not None
    assert check_url("http://0127.0.0.1") is None
    # assert check_url("http://::1") is not None
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


_DNS_253 = "a." * 125 + "abc"  # 253 chars — at the DNS length limit
_DNS_254 = "a." * 125 + "abcd"  # 254 chars — over


@pytest.mark.parametrize(
    "domain, expected",
    [
        ("", False),
        ("a" * 254 + ".com", False),  # exceeds DNS length limit
        (_DNS_253, True),
        (_DNS_254, False),
        ("too-long" + "g" * 60 + ".org", False),
        ("long" + "g" * 50 + ".org", True),
        ("example.-com", False),
        ("example.", False),
        ("-example.com", False),
        ("_example.com", False),
        ("example.com:", False),
        ("a......b.com", False),
        ("*.example.com", False),
        ("exa-mple.co.uk", True),
        ("kräuter.de", True),
        ("xn--h1aagokeh.xn--p1ai", True),
        ("kräuter.de:8080", True),  # port split before IDNA
        ("историк.рф:8888", True),
        ("kräuter.de:99999", False),
        ("ä" * 100 + ".de", False),  # non-ASCII too long to punycode
        ("`$smarty.server.server_name`", False),
        ("$`)}if(a.tryconvertencoding)trycatch(e)const", False),
        ("00x200.jpg,", False),
        ("-100x100.webp", False),
        ("0.gravata.html", False),
        ("https:", False),
        # IPv4
        ("127.0.0.1", True),
        ("::1", True),
        ("900.200.100.75", False),
        ("111.111.111", False),
        ("0127.0.0.1", False),
        ("127.0.0.1:8080", True),
        ("900.200.100.75:8080", False),  # invalid IP, with port
        ("1.2.3.4:65535", True),
        ("1.2.3.4:99999", False),
        ("1.2.3.4:0", False),
        ("1.2.3.4:0080", False),  # leading zero rejected
        # bracketed IPv6
        ("[::1]", True),
        ("[2001:db8::1]", True),
        ("[::1]:8080", True),
        ("[::1]:0", False),
        ("[::1]:0080", False),
        ("[::1]:99999", False),
        ("[not-an-ip]", False),
        ("[::1", False),
        # trailing-dot FQDN
        ("example.com.", True),
        ("www.example.com.", True),
        ("example.com.:8080", True),
        ("192.168.0.1.", True),
        ("192.168.0.1.:8080", True),
        ("example.com..", False),  # multiple trailing dots stay invalid
        # hex-only strings that are not IPs
        ("abc.de", True),
        ("aced.de", True),
        ("dead.beef", True),
        # file extensions / gravatar / numeric
        ("example.jpg", False),
        ("example.html", False),
        ("0.gravatar.com", False),
        ("12345.org", False),
    ],
)
def test_domain_filter(domain, expected):
    "Test filters related to domain and hostnames."
    assert domain_filter(domain) is expected


def test_urlcheck_redirects():
    "Test redirection checks with a mocked HTTP pool."

    def _fake_head(status, location):
        "Stand-in for a urllib3 HEAD response."
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


def test_urlutils():
    """Test URL manipulation tools"""
    # domain extraction
    assert extract_domain("") is None
    assert extract_domain(5) is None
    assert extract_domain("h") is None
    # host splitting (subdomains, compound/IDN suffixes, longest-match) is covered
    # exhaustively by test_tld on get_registrable_domain; the asserts here cover only
    # what the URL layer adds on top: scheme/query/fragment/userinfo/port/IP parsing.
    assert extract_domain("https://httpbun.org/") == "httpbun.org"
    assert extract_domain("https://news.bbc.co.uk/") == "bbc.co.uk"  # representative
    # fast= is accepted for backward compatibility and no longer changes the result
    assert extract_domain("https://www.httpbun.org/", fast=True) == "httpbun.org"
    # query and fragment are stripped
    assert extract_domain("http://example.com?query=one") == "example.com"
    assert extract_domain("http://example.com#fragment") == "example.com"
    # empty domain (userinfo only) yields None
    assert extract_domain("http://exam.p@") is None
    # port stripped cleanly, not glued onto the last label; punycode host + port
    assert (
        extract_domain("http://xn--h1aagokeh.xn--p1ai:8888") == "xn--h1aagokeh.xn--p1ai"
    )
    assert extract_domain("https://user:pass@www.example.com:81/") == "example.com"
    # IPv4: bare, with port, trailing-dot FQDN spelling
    assert extract_domain("https://192.168.0.1/") == "192.168.0.1"
    assert extract_domain("http://192.168.0.1:8080/test") == "192.168.0.1"
    assert extract_domain("http://192.168.0.1./") == "192.168.0.1"
    assert extract_domain("http://example.com../") is None
    # hex IPv4 literals are rejected, not mistaken for domains
    assert extract_domain("http://0xc0.0xa8.0x0.0x1/") is None
    # IPv6: bracketed, bracketed+port, unbracketed, canonicalized regardless of spelling
    assert extract_domain("https://[2001:db8::1]/") == "2001:db8::1"
    assert extract_domain("https://[2001:db8::1]:8080/") == "2001:db8::1"
    assert extract_domain("http://[0:0:0:0:0:0:0:1]/") == "::1"
    assert (
        extract_domain("http://2001:DB8::FF00:42:8329/test") == "2001:db8::ff00:42:8329"
    )
    # unvalidated TLDs accepted by design (no PSL TLD-existence check)
    assert extract_domain("http://domain.test/") == "domain.test"
    # IDN resolves via punycode, returned in original form
    assert extract_domain("https://foo.lødingen.no/") == "foo.lødingen.no"
    # stray / unbalanced brackets must not raise
    assert extract_domain("http://sub.example.com]/x") is None
    assert extract_domain("http://[invalid/") is None
    # url parsing
    result = _parse("https://httpbun.org/")
    assert isinstance(result, SplitResult)
    newresult = _parse(result)
    assert isinstance(newresult, SplitResult)
    with pytest.raises(TypeError):
        result = _parse(1.23)

    assert get_base_url("https://example.org/path") == "https://example.org"
    with pytest.raises(ValueError):
        assert get_host_and_path("123") is None
    assert get_host_and_path("https://example.org/path") == (
        "https://example.org",
        "/path",
    )
    assert get_host_and_path("https://example.org/") == ("https://example.org", "/")
    assert get_host_and_path("https://example.org") == ("https://example.org", "/")
    # query keys that are HTML entity names used to be turned into characters
    assert get_host_and_path("https://example.org/a?b=1&param=2") == (
        "https://example.org",
        "/a?b=1&param=2",
    )
    assert get_host_and_path("https://example.org/a?b=1&sect=2&copy=3") == (
        "https://example.org",
        "/a?b=1&sect=2&copy=3",
    )
    assert get_host_and_path("https://example.org/a?b=1&amp;c=2") == (
        "https://example.org",
        "/a?b=1&c=2",
    )
    assert get_hostinfo("https://httpbun.org/") == (
        "httpbun.org",
        "https://httpbun.org",
    )
    assert get_hostinfo("https://example.org/path") == (
        "example.org",
        "https://example.org",
    )
    # keeping track of known URLs
    known_links = {"https://test.org"}
    assert is_known_link("https://test.org/1", known_links) is False
    assert is_known_link("https://test.org", known_links) is True
    assert is_known_link("http://test.org", known_links) is True
    assert is_known_link("http://test.org/", known_links) is True
    assert is_known_link("https://test.org/", known_links) is True
    # protocol variant: known as http, queried as https (and the reverse)
    assert is_known_link("https://test.org/1", {"http://test.org/1"}) is True
    assert is_known_link("http://test.org/1", {"https://test.org/1"}) is True
    assert is_known_link("https://test.org/1", {"http://test.org/1/"}) is True
    # an empty link must not raise and is never "known"
    assert is_known_link("", known_links) is False
    # filter URLs
    # unique and sorted URLs
    myurls = ["/category/xyz", "/category/abc", "/cat/test", "/category/abc"]
    assert len(filter_urls(myurls, None)) == 3
    assert filter_urls(myurls, "category") == ["/category/abc", "/category/xyz"]
    # feeds
    assert len(filter_urls(["https://feedburner.google.com/aabb"], "category")) == 1
    assert len(filter_urls(["https://feedburner.google.com/aabb"], None)) == 1


@pytest.mark.parametrize(
    "host, expected",
    [
        # standard cases
        ("www.bbc.co.uk", ("bbc", "bbc.co.uk")),
        ("example.com", ("example", "example.com")),
        ("a.b.example.com", ("example", "example.com")),
        ("foo.ne.jp", ("foo", "foo.ne.jp")),
        ("shop.example.org.au", ("example", "example.org.au")),
        # IPv4 / numeric final label rejected
        ("192.168.0.1", (None, None)),
        ("www.example.42", (None, None)),
        ("example.４２", ("example", "example.４２")),  # fullwidth digits are ordinary
        # hex IPv4 rejected like decimal
        ("0xc0.0xa8.0x0.0x1", (None, None)),
        ("foo.0x1", (None, None)),
        ("foo.0x", (None, None)),
        # IPv6 (colons) rejected
        ("2001:db8::1", (None, None)),
        ("::ffff:192.0.2.128", (None, None)),
        # trailing-dot FQDN normalized
        ("www.example.com.", ("example", "example.com")),
        # malformed / edge cases
        ("", (None, None)),
        (None, (None, None)),
        ("localhost", (None, None)),
        ("a..b.com", (None, None)),
        (".uk", (None, None)),
        (".foo.ck", (None, None)),  # leading dot + bare wildcard suffix
        # suffix-set boundary
        ("sub.unknown.xyz", ("unknown", "unknown.xyz")),
        ("blog.ax", ("blog", "blog.ax")),
        # bare public suffix
        ("co.uk", (None, None)),
        # www IS the registrable label
        ("www.co.uk", ("www", "www.co.uk")),
        ("www.gov.uk", ("www", "www.gov.uk")),
        # case-insensitive matching, original case kept
        ("BBC.CO.UK", ("BBC", "BBC.CO.UK")),
        ("Example.COM", ("Example", "Example.COM")),
        ("FOO.CK", (None, None)),
        ("X.CITY.KOBE.JP", ("CITY", "CITY.KOBE.JP")),
        ("FOO.LØDINGEN.NO", ("FOO", "FOO.LØDINGEN.NO")),
        # full-PSL coverage
        ("x.co.tz", ("x", "x.co.tz")),
        # 3-label suffix via longest-match
        ("school.act.edu.au", ("school", "school.act.edu.au")),
        # Unicode and xn-- suffix forms
        ("foo.lødingen.no", ("foo", "foo.lødingen.no")),
        ("foo.xn--ldingen-q1a.no", ("foo", "foo.xn--ldingen-q1a.no")),
        # ICANN-only: private-suffix hosts resolve as ordinary domains
        ("user.github.io", ("github", "github.io")),
        # wildcard (*.) and exception (!) PSL rules
        ("www.foo.ck", ("www", "www.foo.ck")),
        ("foo.ck", (None, None)),
        ("www.ck", ("www", "www.ck")),  # !www.ck exception
        ("a.b.kobe.jp", ("a", "a.b.kobe.jp")),
        ("x.city.kobe.jp", ("city", "city.kobe.jp")),  # !city.kobe.jp exception
        ("foo.sch.uk", (None, None)),
        ("bar.foo.sch.uk", ("bar", "bar.foo.sch.uk")),
    ],
)
def test_tld(host, expected):
    "Test get_registrable_domain."
    assert get_registrable_domain(host) == expected


def test_tld_idna_fallback():
    "Overlong non-ASCII label falls back instead of raising."
    overlong_cjk = "".join(chr(0x4E00 + i) for i in range(50))
    assert _idna_label(overlong_cjk) == overlong_cjk
    assert get_registrable_domain(f"{overlong_cjk}.example.com") == (
        "example",
        "example.com",
    )


@pytest.mark.parametrize("base", sorted(WILDCARD_BASES))
def test_tld_wildcard_bases(base):
    "Round-trip every hardcoded PSL wildcard base to catch a stale/typo'd entry."
    assert get_registrable_domain(f"x.{base}") == (None, None)
    assert get_registrable_domain(f"a.b.{base}") == ("a", f"a.b.{base}")


@pytest.mark.parametrize("exception", sorted(EXCEPTIONS))
def test_tld_exceptions(exception):
    "Round-trip every hardcoded PSL exception to catch a stale/typo'd entry."
    domain = exception.split(".")[0]
    assert get_registrable_domain(exception) == (domain, exception)
    assert get_registrable_domain(f"sub.{exception}") == (domain, exception)


def test_psl_data_encoder_consistency():
    "Generated data must be ASCII and its xn-- labels must round-trip through the runtime encoder."
    checked = 0
    for ruleset in (MULTI_PART_SUFFIXES, WILDCARD_BASES, EXCEPTIONS):
        for rule in ruleset:
            assert rule.isascii(), rule
            for label in rule.split("."):
                if label.startswith("xn--"):
                    assert _idna_encode(label.encode("ascii").decode("idna")) == label
                    checked += 1
    assert checked  # the data does contain punycode entries


def test_psl_check_ignores_header_metadata():
    "--check compares rule data, not the VERSION/COMMIT provenance header."
    from scripts.update_psl import render, strip_header_metadata

    old = render(["co.uk"], ["ck"], ["www.ck"], "v1", "aaa")
    new = render(["co.uk"], ["ck"], ["www.ck"], "v2", "bbb")
    assert old != new  # headers differ
    assert strip_header_metadata(old) == strip_header_metadata(new)  # rules identical
    changed = render(["co.uk", "gov.uk"], ["ck"], ["www.ck"], "v1", "aaa")
    assert strip_header_metadata(old) != strip_header_metadata(changed)


def test_psl_parsers():
    "PSL text parsing: header fields, ICANN-only rule extraction, rule-set split."
    from scripts.update_psl import (
        build_rule_sets,
        extract_icann_rules,
        extract_version_commit,
    )

    raw = (
        "// VERSION: 2026-07-15_00-00-00_UTC\n"
        "// COMMIT: abc123\n"
        "// ===BEGIN ICANN DOMAINS===\n"
        "// a comment\n"
        "com\n"  # single-label TLD -> dropped by build_rule_sets
        "co.uk\n"
        "\n"  # blank line
        "*.ck\n"
        "!www.ck\n"
        "  ne.jp  \n"  # whitespace stripped
        "// ===END ICANN DOMAINS===\n"
        "// ===BEGIN PRIVATE DOMAINS===\n"
        "github.io\n"  # private section -> excluded
        "// ===END PRIVATE DOMAINS===\n"
    )
    assert extract_version_commit(raw) == ("2026-07-15_00-00-00_UTC", "abc123")
    assert extract_version_commit("no headers") == ("unknown", "unknown")

    rules = extract_icann_rules(raw)
    assert rules == ["com", "co.uk", "*.ck", "!www.ck", "ne.jp"]  # ICANN only

    suffixes, wildcards, exceptions = build_rule_sets(rules)
    assert suffixes == ["co.uk", "ne.jp"]  # single-label "com" dropped
    assert wildcards == ["ck"]  # "*." stripped
    assert exceptions == ["www.ck"]  # "!" stripped

    # missing markers hard-fail (intended for a generator script)
    with pytest.raises(IndexError):
        extract_icann_rules("no markers")


def test_psl_main_exit_codes():
    "main() maps every data-error channel to exit 2, distinct from --check's exit 1."
    import urllib3

    import scripts.update_psl as update_psl

    # HTTP-status failure (RuntimeError from fetch_psl)
    with patch.object(
        update_psl,
        "fetch_psl",
        side_effect=RuntimeError("PSL download failed: HTTP 503"),
    ):
        assert update_psl.main() == 2

    # network failure (urllib3.exceptions.HTTPError, e.g. MaxRetryError)
    with patch.object(
        update_psl,
        "fetch_psl",
        side_effect=urllib3.exceptions.MaxRetryError(None, "url"),  # type: ignore[arg-type]
    ):
        assert update_psl.main() == 2

    # malformed PSL text: markers missing -> IndexError from extract_icann_rules
    with patch.object(update_psl, "fetch_psl", return_value="no markers here"):
        assert update_psl.main() == 2


def test_external():
    """test domain comparison"""
    assert is_external("", "https://www.microsoft.com/") is True
    assert is_external("https://github.com/", "https://www.microsoft.com/") is True
    assert (
        is_external(
            "https://microsoft.com/", "https://www.microsoft.com/", ignore_suffix=True
        )
        is False
    )
    assert (
        is_external(
            "https://microsoft.com/", "https://www.microsoft.com/", ignore_suffix=False
        )
        is False
    )
    assert (
        is_external(
            "https://google.com/", "https://www.google.co.uk/", ignore_suffix=True
        )
        is False
    )
    assert (
        is_external(
            "https://google.com/", "https://www.google.co.uk/", ignore_suffix=False
        )
        is True
    )
    # compound suffixes: same registrable domain, different subdomains
    assert (
        is_external(
            "https://a.example.co.uk/", "https://b.example.co.uk/", ignore_suffix=False
        )
        is False
    )
    # compound suffixes: different registrable domains under same ccSLD
    assert (
        is_external("https://x.co.uk/", "https://y.co.uk/", ignore_suffix=False) is True
    )
    # same IP in different textual forms is the same host
    assert is_external("http://[::1]/", "http://[0:0:0:0:0:0:0:1]/") is False
    assert is_external("http://192.168.0.1/", "http://192.168.0.1./") is False
    # malformed URLs
    assert is_external("h1234", "https://www.google.co.uk/", ignore_suffix=True) is True
    # stray bracket in the netloc must not raise
    assert is_external("http://sub.example.com]/x", "https://example.com/") is True


def test_extraction():
    """test link comparison in HTML"""
    with pytest.raises(ValueError):
        extract_links(None, base_url="https://test.com/", external_bool=False)
    assert not extract_links(None, url="https://test.com/", external_bool=False)
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
    assert len(extract_links(pagecontent, "https://test.org", False)) == 1
    # nofollow
    pagecontent = '<html><a href="https://test.com/example" rel="nofollow ugc"/></html>'
    assert not extract_links(pagecontent, "https://test.com/", False)
    pagecontent = '<html><a href="https://test.com/rel/nofollow-guide"/></html>'
    assert len(extract_links(pagecontent, "https://test.com/", False)) == 1
    # language
    pagecontent = '<html><a href="https://test.com/example" hreflang="de-DE"/></html>'
    assert len(extract_links(pagecontent, "https://test.com/", False)) == 1
    assert not extract_links(pagecontent, "https://test.com/", True)
    assert (
        len(extract_links(pagecontent, "https://test.com/", False, language="de")) == 1
    )
    assert not extract_links(pagecontent, "https://test.com/", False, language="en")
    pagecontent = "<html><a href=https://test.com/example hreflang=de-DE/></html>"
    assert (
        len(extract_links(pagecontent, "https://test.com/", False, language="de")) == 1
    )
    # x-default
    pagecontent = (
        '<html><a href="https://test.com/example" hreflang="x-default"/></html>'
    )
    assert (
        len(extract_links(pagecontent, "https://test.com/", False, language="de")) == 1
    )
    assert (
        len(extract_links(pagecontent, "https://test.com/", False, language="en")) == 1
    )
    pagecontent = '<html><a href="https://test.com/example" hreflang="DE-DE"/></html>'
    assert (
        len(extract_links(pagecontent, "https://test.com/", False, language="de")) == 1
    )
    assert not extract_links(pagecontent, "https://test.com/", False, language="en")
    pagecontent = (
        '<html><a href="https://test.com/example" hreflang="X-DEFAULT"/></html>'
    )
    assert (
        len(extract_links(pagecontent, "https://test.com/", False, language="de")) == 1
    )
    # language + content
    pagecontent = '<html><a hreflang="de-DE" href="https://test.com/example"/><a href="https://test.com/example2"/><a href="https://test.com/example2 ADDITIONAL"/></html>'
    links = extract_links(pagecontent, "https://test.com/", external_bool=False)
    assert sorted(links) == ["https://test.com/example", "https://test.com/example2"]
    assert (
        len(
            extract_links(
                pagecontent, "https://test.com/", external_bool=False, language="de"
            )
        )
        == 2
    )
    pagecontent = '<html><a hreflang="de-DE" href="https://test.com/example"/><a href="https://test.com/page/2"/></html>'
    assert (
        len(
            extract_links(
                pagecontent, "https://test.com/", external_bool=False, with_nav=False
            )
        )
        == 1
    )
    assert (
        len(
            extract_links(
                pagecontent, "https://test.com/", external_bool=False, with_nav=True
            )
        )
        == 2
    )


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
    links = extract_links(
        pagecontent, url="https://httpbun.org", external_bool=False, with_nav=True
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
    print(links)
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
    assert len(extract_links(pagecontent)) == 2
    assert len(extract_links(pagecontent, external_bool=True)) == 2
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
    "Test the filter_links helper."
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
    from urllib.robotparser import RobotFileParser

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


def test_cli(tmp_path):
    """test the command-line interface"""
    testargs = [
        "-i", "input.txt",
        "-d", "discardedfile.txt",
        "--outputfile", "output.txt",
        "-v",
        "--language", "en",
        "--parallel", "2",
    ]  # fmt: skip
    args = cli.parse_args(testargs)
    assert args.inputfile == "input.txt"
    assert args.discardedfile == "discardedfile.txt"
    assert args.outputfile == "output.txt"
    assert args.verbose is True
    assert args.language == "en"
    assert args.parallel == 2
    assert os.system("courlan --help") == 0  # exit status

    # _cli_check_urls
    assert cli._cli_check_urls(["123", "https://example.org"]) == [
        (False, "123"),
        (True, "https://example.org"),
    ]

    # testfile
    inputfile = os.path.join(RESOURCES_DIR, "input.txt")
    outputfile = str(tmp_path / "output.txt")
    env = os.environ.copy()
    # Force encoding to utf-8 for Windows (seems to be a problem only in GitHub Actions)
    if os.name == "nt":
        env["PYTHONIOENCODING"] = "utf-8"
        courlan_bin = os.path.join(sys.prefix, "Scripts", "courlan")
    else:
        courlan_bin = "courlan"
    # test for Windows and the rest
    assert (
        subprocess.run(
            [courlan_bin, "-i", inputfile, "-o", outputfile, "-p", "1"],
            env=env,
            check=False,
        ).returncode
        == 0
    )

    # tests without Windows
    if os.name != "nt":
        f = io.StringIO()
        # dry run with processing
        testargs = [
            "-i", inputfile,
            "-d", str(tmp_path / "discarded.txt"),
            "-o", outputfile,
            "--language", "en",
            "--strict",
            "-p", "1",
        ]  # fmt: skip
        with redirect_stdout(f):
            cli.process_args(cli.parse_args(testargs))
        assert not f.getvalue()

        # dry run with sampling
        testargs = ["-i", inputfile, "-o", str(tmp_path / "sample.txt"), "--sample", "10"]  # fmt: skip
        args = cli.parse_args(testargs)
        with redirect_stdout(f):
            cli.process_args(args)
        assert not f.getvalue()
        args.verbose = True
        with redirect_stdout(f):
            cli.process_args(args)
        assert not f.getvalue()


def test_cli_main(tmp_path):
    """test the main() entry point"""
    inputfile = os.path.join(RESOURCES_DIR, "input.txt")
    outputfile = str(tmp_path / "output.txt")
    testargs = ["", "-i", inputfile, "-o", outputfile, "--sample", "10"]
    with patch.object(sys, "argv", testargs):
        cli.main()


def test_cli_discardedfile(tmp_path):
    """discarded URLs are written newline-separated to the discard file"""
    inputfile = tmp_path / "input.txt"
    inputfile.write_text("https://example.org/valid\nhttp://ab\nnot-a-url\n")
    outputfile = tmp_path / "output.txt"
    discardfile = tmp_path / "discarded.txt"
    testargs = [
        "-i", str(inputfile),
        "-o", str(outputfile),
        "-d", str(discardfile),
        "-p", "1",
    ]  # fmt: skip
    cli._cli_process(cli.parse_args(testargs))
    discarded = discardfile.read_text().splitlines()
    assert "http://ab" in discarded and "not-a-url" in discarded


def test_cli_no_discardfile(tmp_path):
    """invalid URLs are dropped silently when no discard file is given"""
    inputfile = tmp_path / "input.txt"
    inputfile.write_text("https://example.org/valid\nnot-a-url\n")
    outputfile = tmp_path / "output.txt"
    testargs = ["-i", str(inputfile), "-o", str(outputfile), "-p", "1"]
    args = cli.parse_args(testargs)
    assert args.discardedfile is None
    cli._cli_process(args)
    assert outputfile.read_text().splitlines() == ["https://example.org/valid"]


def test_sample():
    """test URL sampling"""
    assert not list(sample_urls(["http://test.org/test1", "http://test.org/test2"], 0))
    assert not list(sample_urls(["http://test.org/", "http://test.org"], 10))

    # assert len(sample_urls(['http://test.org/test1', 'http://test.org/test2'], 1)) == 1
    mylist = [
        "http://t.o/t1",
        "http://test.org/test1",
        "http://test.org/test2",
        "http://test2.org/test2",
    ]
    assert len(sample_urls(mylist, 1, verbose=True)) == 2
    assert not sample_urls(mylist, 1, exclude_min=10, verbose=True)
    assert len(sample_urls(mylist, 1, exclude_max=1, verbose=True)) == 1
    bound_urls = [f"http://bound.org/{i}" for i in range(3)]
    assert len(sample_urls(bound_urls, 10, exclude_min=3)) == 3
    assert not sample_urls(bound_urls, 10, exclude_min=4)

    test_urls = [f"https://test.org/{a}" for a in range(1000)]
    example_urls = [f"https://www.example.org/{a}" for a in range(100)]
    other_urls = [f"https://www.other.org/{a}" for a in range(10000)]
    urls = test_urls + example_urls + other_urls
    sample = sample_urls(urls, 10)
    assert len([u for u in sample if "test.org" in u]) == 10
    assert len([u for u in sample if "example.org" in u]) == 10
    assert len([u for u in sample if "other.org" in u]) == 10
    sample = sample_urls(urls, 150)
    assert len([u for u in sample if "test.org" in u]) == 150
    assert len([u for u in sample if "example.org" in u]) == 100
    assert len([u for u in sample if "other.org" in u]) == 150


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
    "Test package meta functions."
    _ = langcodes_score("en", "en_HK")
    _ = get_registrable_domain("www.example.com")
    _ = _parse("https://example.net/123/abc")

    # urlsplit is only an lru_cache wrapper on some Python versions
    has_urlsplit_cache = hasattr(urlsplit, "cache_info")
    assert langcodes_score.cache_info().currsize > 0
    assert get_registrable_domain.cache_info().currsize > 0
    if has_urlsplit_cache:
        assert urlsplit.cache_info().currsize > 0

    clear_caches()

    assert langcodes_score.cache_info().currsize == 0
    assert get_registrable_domain.cache_info().currsize == 0
    if has_urlsplit_cache:
        assert urlsplit.cache_info().currsize == 0


# --- mutation-gap tests ---


def test_extract_links_loop_resilience():
    "Filtered/invalid/duplicate links must not prevent extraction of later valid links."
    # nofollow before valid link
    html = '<html><a href="https://test.com/skip" rel="nofollow"/><a href="https://test.com/keep"/></html>'
    assert "https://test.com/keep" in extract_links(html, "https://test.com/", False)
    # invalid link before valid
    html = '<html><a href="http://t.g/x"/><a href="https://test.com/ok"/></html>'
    result = extract_links(html, "https://test.com/", False)
    assert "https://test.com/ok" in result
    # duplicate before unique
    html = '<html><a href="https://test.com/a"/><a href="https://test.com/a"/><a href="https://test.com/b"/></html>'
    result = extract_links(html, "https://test.com/", False)
    assert "https://test.com/a" in result and "https://test.com/b" in result


def test_clean_url_protocol_detection():
    "Double-URL detection must not fire on single-protocol URLs."
    # single protocol — must survive unchanged
    assert clean_url("http://example.org/page") == "http://example.org/page"
    # double protocol — inner URL extracted
    result = clean_url("http://redirect.com/?url=http://real.com/page")
    assert "real.com" in result


def test_scrub_url_trailing_slash():
    "Trailing-slash strip fires on root URLs (3 slashes) but not on paths."
    # path with trailing slash preserved
    assert scrub_url("http://example.org/path/") == "http://example.org/path/"
    # root URL (exactly 3 slashes) gets stripped
    assert scrub_url("http://example.org/") == "http://example.org"


def test_clean_query_param_ordering():
    "Strict: disallowed param must not prevent later allowed params. Tracker likewise."
    # strict: disallowed 'badparam' then allowed 'page'
    result = clean_query("badparam=1&page=2", strict=True)
    assert "page=2" in result
    assert "badparam" not in result
    # tracker then non-tracker
    result = clean_query("utm_source=twitter&title=hello", strict=False)
    assert "title=hello" in result
    assert "utm_source" not in result


def test_normalize_path_leading_dotdot():
    "Leading /../ segments are collapsed."
    assert normalize_path("/../foo/bar") == "/foo/bar"
    assert normalize_path("/../../a/b") == "/a/b"
    assert normalize_path("/a/../b") == "/a/../b"  # only leading ones


def test_basic_filter_boundaries():
    "basic_filter boundary: 10-char URL passes, 9-char fails; non-http rejected."
    assert basic_filter("http://x.y") is True  # exactly 10
    assert basic_filter("http://x.") is False  # 9 chars
    assert basic_filter("ftp://example.org/page") is False  # non-http, >10 chars
    assert basic_filter("httpx://example.org") is True  # starts with "http"


def test_notcrawlable_schemes():
    "NOTCRAWLABLE catches javascript:, mailto:, tel:, whatsapp: in path."
    assert path_filter("/javascript:void(0)", "") is False
    assert path_filter("/mailto:user@example.com", "") is False
    assert path_filter("/tel:+1234567890", "") is False
    assert path_filter("/whatsapp:send", "") is False
    assert path_filter("/normal-page", "") is True


def test_strip_trailing_dot_edge_cases():
    "Double trailing dots stay invalid; userinfo+port handled."
    assert _strip_trailing_dot("example.com.") == "example.com"
    assert _strip_trailing_dot("example.com..") == "example.com.."
    assert _strip_trailing_dot("example.com.:8080") == "example.com:8080"
    # with userinfo — the host:port branch should not fire
    assert _strip_trailing_dot("user@example.com.:80") == "user@example.com.:80"


def test_get_tldinfo_ipv6():
    "IPv6 addresses through get_tldinfo."
    from courlan.urlutils import get_tldinfo

    # bracketed IPv6
    assert get_tldinfo("https://[2001:db8::1]/path") == ("2001:db8::1", "2001:db8::1")
    # unbracketed IPv6 (2 colons minimum)
    assert get_tldinfo("http://2001:db8::1/path") == ("2001:db8::1", "2001:db8::1")


def test_hosts_hex_labels():
    "Hex numeric labels (0xAB) detected as numeric, preventing domain registration."
    from courlan.hosts import _is_numeric_label

    assert _is_numeric_label("0xAB") is True
    assert _is_numeric_label("0xA") is True
    assert _is_numeric_label("0x") is True  # empty hex digits
    assert _is_numeric_label("0xGG") is False
    assert _is_numeric_label("123") is True
    assert _is_numeric_label("abc") is False
