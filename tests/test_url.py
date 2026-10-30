"""
Unit tests for the courlan package: URL cleaning, filtering and utilities.
"""

from urllib.parse import SplitResult, urlsplit

import pytest

from courlan import (
    check_url,
    clean_url,
    extract_domain,
    extract_links,
    filter_urls,
    fix_relative_urls,
    get_base_url,
    get_host_and_path,
    get_hostinfo,
    is_navigation_page,
    is_not_crawlable,
    is_valid_url,
    lang_filter,
    normalize_url,
    scrub_url,
    validate_url,
)
from courlan.clean import clean_query, normalize_and_split, normalize_path
from courlan.filters import (
    basic_filter,
    extension_filter,
    path_filter,
    type_filter,
)
from courlan.langcodes import langcodes_score
from courlan.urlutils import _parse, _strip_trailing_dot, is_known_link


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


SUB = "https://www.example.org/dir/subdir/file.html"


@pytest.mark.parametrize(
    "base, link, expected",
    [
        ("https://example.org", "page.html", "https://example.org/page.html"),
        (
            "http://example.org",
            "//example.org/page.html",
            "http://example.org/page.html",
        ),
        ("https://example.org", "./page.html", "https://example.org/page.html"),
        ("https://example.org", "/page.html", "https://example.org/page.html"),
        # fixing partial URLs
        (
            "https://example.org",
            "https://example.org/test.html",
            "https://example.org/test.html",
        ),
        (
            "https://example.org",
            "//example.org/test.html",
            "https://example.org/test.html",
        ),
        ("https://example.org", "../../test.html", "https://example.org/test.html"),
        # sub-directories
        (SUB, "/absolute", "https://www.example.org/absolute"),
        (SUB, "relative", "https://www.example.org/dir/subdir/relative"),
        (
            "https://www.example.org/dir/subdir/",
            "relative",
            "https://www.example.org/dir/subdir/relative",
        ),
        (
            "https://www.example.org/dir/subdir",
            "relative",
            "https://www.example.org/dir/relative",
        ),
        # non-relative URLs
        ("https://example.org", "https://www.eff.org", "https://www.eff.org"),
        ("https://example.org", "//www.eff.org", "https://www.eff.org"),
        ("http://example.org", "//www.eff.org", "http://www.eff.org"),
        ("http://example.org", "https://www.eff.org", "https://www.eff.org"),
        # looks like an absolute URL but is actually a valid relative URL
        ("https://example.org", "www.eff.org", "https://example.org/www.eff.org"),
        # misc
        (SUB, "./this:that", "https://www.example.org/dir/subdir/this:that"),
        (
            "https://www.example.org/test.html?q=test#frag",
            "foo.html?q=bar#baz",
            "https://www.example.org/foo.html?q=bar#baz",
        ),
        ("https://www.example.org", "{privacy}", "{privacy}"),
    ],
)
def test_fix_relative(base, link, expected):
    assert fix_relative_urls(base, link) == expected


def test_fix_relative_malformed():
    # malformed URLs raise, extract_links skips them and keeps the page
    for base, link in (
        ("https://example.org", "//[zz]/x"),
        ("https://[zz]", "/page.html"),
        ("https://httpbun.com", "http://[::1"),
    ):
        with pytest.raises(ValueError):
            fix_relative_urls(base, link)
    for no_filter in (False, True):
        assert extract_links(
            '<a href="//[zz]/x">a</a><a href="/ok">b</a>',
            "https://example.org",
            no_filter=no_filter,
        ) == {"https://example.org/ok"}


def test_scrub():
    # clean: scrub + normalize
    assert clean_url(5) is None  # type: ignore[arg-type]
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
    assert validate_url("ntp://www.test.org/test")[0] is False
    assert validate_url("ftps://www.test.org/test")[0] is False
    assert validate_url("http://t.g/test")[0] is False
    assert validate_url("http://test.org/test")[0] is True

    assert not is_valid_url("http://www.test[.org/test")
    assert is_valid_url("http://test.org/test")
    # non-string input
    assert not is_valid_url(None)
    assert not is_valid_url(123)  # type: ignore[arg-type]
    assert not is_valid_url(b"http://test.org/test")  # type: ignore[arg-type]

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
    assert normalize_path("/a/../b") == "/a/../b"  # only leading ones

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


def test_urlutils():
    # domain extraction
    assert extract_domain("") is None
    assert extract_domain(5) is None  # type: ignore[arg-type]
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
        result = _parse(1.23)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        get_host_and_path("123")
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
    assert filter_urls(myurls, None) == ["/cat/test", "/category/abc", "/category/xyz"]
    assert filter_urls(myurls, "category") == ["/category/abc", "/category/xyz"]
    # feeds
    feeds = ["https://feedburner.google.com/aabb"]
    assert filter_urls(feeds, "category") == filter_urls(feeds, None) == feeds


def test_clean_url_protocol_detection():
    "Double-URL detection must not fire on single-protocol URLs."
    # single protocol, unchanged
    assert clean_url("http://example.org/page") == "http://example.org/page"
    # double protocol, inner URL extracted
    result = clean_url("http://redirect.com/?url=http://real.com/page")
    assert result == "http://real.com/page"


def test_scrub_url_trailing_slash():
    "Trailing-slash strip fires on root URLs (3 slashes) but not on paths."
    # path with trailing slash preserved
    assert scrub_url("http://example.org/path/") == "http://example.org/path/"
    # root URL (exactly 3 slashes) gets stripped
    assert scrub_url("http://example.org/") == "http://example.org"


def test_clean_query_param_ordering():
    "Strict: disallowed param must not prevent later allowed params. Tracker likewise."
    # strict: disallowed 'badparam' then allowed 'page'
    assert clean_query("badparam=1&page=2", strict=True) == "page=2"
    # tracker then non-tracker
    assert clean_query("utm_source=twitter&title=hello", strict=False) == "title=hello"


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
    # with userinfo, the host:port branch should not fire
    assert _strip_trailing_dot("user@example.com.:80") == "user@example.com.:80"
