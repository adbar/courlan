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
from courlan.core import filter_links
from courlan.filters import (
    domain_filter,
    extension_filter,
    langcodes_score,
    path_filter,
    type_filter,
)
from courlan.meta import clear_caches
from courlan.network import redirection_test
from courlan.urlutils import _parse, is_known_link

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
RESOURCES_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data")


def test_baseurls():
    assert get_base_url("https://example.org/") == "https://example.org"
    assert (
        get_base_url("https://example.org/test.html?q=test#frag")
        == "https://example.org"
    )
    assert get_base_url("example.org") == ""


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


def test_scrub():
    # clean: scrub + normalize
    assert clean_url(5) is None
    assert clean_url("ø\xaa") == "%C3%B8%C2%AA"
    assert clean_url("https://example.org/?p=100") == "https://example.org/?p=100"
    assert clean_url("https://example.org/ab'c") == "https://example.org/ab%27c"
    assert clean_url('https://example.org/abc"') == "https://example.org/abc"
    assert clean_url("https://example.org/abc<") == "https://example.org/abc"
    assert clean_url("https://example.org/\t?p=100") == "https://example.org/?p=100"
    assert (
        clean_url("https://example.org:443/file.html?p=100&abc=1#frag")
        == "https://example.org/file.html?abc=1&p=100#frag"
    )
    # clean_url must be idempotent: stripping every query parameter from a
    # root path used to leave a trailing slash that a second pass removed,
    # so the canonical form depended on how many times it was applied.
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


def test_extension_filter():
    _, parsed_url = validate_url("http://www.example.org/test.js")
    assert extension_filter(parsed_url.path) is False
    _, parsed_url = validate_url("http://goodbasic.com/GirlInfo.aspx?Pseudo=MilfJanett")
    assert extension_filter(parsed_url.path) is True
    _, parsed_url = validate_url(
        "https://www.familienrecht-allgaeu.de/de/vermoegensrecht.amp"
    )
    assert extension_filter(parsed_url.path) is True
    _, parsed_url = validate_url("http://www.example.org/test.shtml")
    assert extension_filter(parsed_url.path) is True
    _, parsed_url = validate_url("http://de.artsdot.com/ADC/Art.nsf/O/8EWETN")
    assert extension_filter(parsed_url.path) is True
    _, parsed_url = validate_url("http://de.artsdot.com/ADC/Art.nsf?param1=test")
    assert extension_filter(parsed_url.path) is False
    _, parsed_url = validate_url("http://www.example.org/test.xhtml?param1=this")
    assert extension_filter(parsed_url.path) is True
    _, parsed_url = validate_url("http://www.example.org/test.php5")
    assert extension_filter(parsed_url.path) is True
    _, parsed_url = validate_url("http://www.example.org/test.php6")
    assert extension_filter(parsed_url.path) is True
    # uppercase extensions are treated like their lowercase forms
    assert extension_filter("/photo.JPG") is False
    assert extension_filter("/page.HTML") is True
    assert extension_filter("/index.PHP") is True


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
    # assert path_filter("/", "") is False


def test_lang_filter():
    assert lang_filter("http://test.com/az", "de", trailing_slash=False) is False
    assert lang_filter("http://test.com/az/", "de") is False
    assert lang_filter("http://test.com/de", "de", trailing_slash=False) is True
    assert lang_filter("http://test.com/de/", "de") is True
    assert (
        lang_filter(
            "https://www.20min.ch/fr/story/des-millions-pour-produire-de-l-energie-renouvelable-467974085377",
            None,
        )
        is True
    )
    assert (
        lang_filter(
            "https://www.20min.ch/fr/story/des-millions-pour-produire-de-l-energie-renouvelable-467974085377",
            "de",
        )
        is False
    )
    assert (
        lang_filter(
            "https://www.20min.ch/fr/story/des-millions-pour-produire-de-l-energie-renouvelable-467974085377",
            "fr",
        )
        is True
    )
    assert (
        lang_filter(
            "https://www.20min.ch/fr/story/des-millions-pour-produire-de-l-energie-renouvelable-467974085377",
            "en",
        )
        is False
    )
    assert (
        lang_filter(
            "https://www.20min.ch/fr/story/des-millions-pour-produire-de-l-energie-renouvelable-467974085377",
            "es",
        )
        is False
    )
    assert lang_filter("https://www.sitemaps.org/en_GB/protocol.html", "en") is True
    assert lang_filter("https://www.sitemaps.org/en_GB/protocol.html", "de") is False
    assert lang_filter("https://en.wikipedia.org/", "de", strict=True) is False
    assert lang_filter("https://en.wikipedia.org/", "de", strict=False) is True
    assert lang_filter("https://de.wikipedia.org/", "de", strict=True) is True
    assert (
        lang_filter(
            "http://de.musclefood.com/neu/neue-nahrungsergaenzungsmittel.html",
            "de",
            strict=True,
        )
        is True
    )
    assert (
        lang_filter(
            "http://de.musclefood.com/neu/neue-nahrungsergaenzungsmittel.html",
            "fr",
            strict=True,
        )
        is False
    )
    assert (
        lang_filter("http://ch.postleitzahl.org/sankt_gallen/liste-T.html", "fr")
        is True
    )
    assert (
        lang_filter("http://ch.postleitzahl.org/sankt_gallen/liste-T.html", "de")
        is True
    )
    # to complete when language mappings are more extensive
    # assert lang_filter('http://ch.postleitzahl.org/sankt_gallen/liste-T.html', 'es') is False
    # disturbing path sub-elements
    assert (
        lang_filter(
            "http://www.uni-rostock.de/fakult/philfak/fkw/iph/thies/mythos.html", "de"
        )
        is True
    )
    assert (
        lang_filter("http://stifter.literature.at/witiko/htm/h15-22b.html", "de")
        is True
    )
    assert (
        lang_filter("http://stifter.literature.at/doc/witiko/h15-22b.html", "de")
        is True
    )
    assert (
        lang_filter("http://stifter.literature.at/nl/witiko/h15-22b.html", "de")
        is False
    )
    assert (
        lang_filter("http://stifter.literature.at/de_DE/witiko/h15-22b.html", "de")
        is True
    )
    assert (
        lang_filter("http://stifter.literature.at/en_US/witiko/h15-22b.html", "de")
        is False
    )
    assert (
        lang_filter(
            "http://www.stiftung.koerber.de/bg/recherche/de/beitrag.php?id=15132&refer=",
            "de",
        )
        is True
    )
    assert (
        lang_filter("http://www.solingen-internet.de/si-hgw/eiferer.htm", "de") is True
    )
    assert (
        lang_filter(
            "http://ig.cs.tu-berlin.de/oldstatic/w2000/ir1/aufgabe2/ir1-auf2-gr16.html",
            "de",
            strict=True,
        )
        is True
    )
    assert (
        lang_filter(
            "http://ig.cs.tu-berlin.de/oldstatic/w2000/ir1/aufgabe2/ir1-auf2-gr16.html",
            "de",
            strict=False,
        )
        is True
    )
    assert (
        lang_filter("http://bz.berlin1.de/kino/050513/fans.html", "de", strict=False)
        is True
    )
    assert (
        lang_filter("http://bz.berlin1.de/kino/050513/fans.html", "de", strict=True)
        is False
    )
    # both path segments differ from target — was always True when two-occurrence branch was dead
    assert lang_filter("https://x.com/fr/x/de/", "en") is False
    # invalid territory (en_XY) is not a confident match, so the de segment wins (0, -1 → -1)
    assert lang_filter("https://x.com/en_XY/x/de/", "en") is False

    # assert lang_filter('http://www.verfassungen.de/ch/basel/verf03.htm'. 'de') is True
    # assert lang_filter('http://www.uni-stuttgart.de/hi/fnz/lehrveranst.html', 'de') is True
    # http://www.wildwechsel.de/ww/front_content.php?idcatart=177&lang=4&client=6&a=view&eintrag=100&a=view&eintrag=0&a=view&eintrag=20&a=view&eintrag=80&a=view&eintrag=20


def test_langcodes_score():
    assert langcodes_score("en", "en_HK") == 1
    assert langcodes_score("en", "en-HK") == 1
    assert langcodes_score("en", "de_DE") == -1
    assert langcodes_score("en", "de-DE") == -1
    assert langcodes_score("en", "en_XY") == 0  # invalid territory
    assert langcodes_score("en", "en-XY") == 0
    assert langcodes_score("en", "xx") == 0  # invalid language
    assert langcodes_score("en", "xx_US") == 0
    assert langcodes_score("en", None) == 0  # non-string input


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


def test_normalization():
    assert normalize_url("HTTPS://WWW.DWDS.DE/") == "https://www.dwds.de/"
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

    # IPv6: default port stripped (was missed by the old \w-lookbehind regex)
    assert normalize_url("http://[::1]:80/") == "http://[::1]/"
    assert normalize_url("https://[::1]:443/") == "https://[::1]/"
    # non-default port preserved
    assert normalize_url("http://[::1]:8080/") == "http://[::1]:8080/"

    # punycode
    assert normalize_url("http://xn--Mnchen-3ya.de") == "http://münchen.de"
    assert normalize_url("http://Mnchen-3ya.de") == "http://mnchen-3ya.de"
    assert normalize_url("http://xn--München.de") == "http://xn--münchen.de"

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
    assert normalize_url("http://test.org/?s_cid=123&clickid=1") == "http://test.org/"
    assert normalize_url("http://test.org/?aftr_source=0") == "http://test.org/"
    assert normalize_url("http://test.org/?fb_ref=0") == "http://test.org/"
    assert normalize_url("http://test.org/?this_affiliate=0") == "http://test.org/"
    assert (
        normalize_url("http://test.org/?utm_source=rss&utm_medium=rss")
        == "http://test.org/"
    )
    assert (
        normalize_url("http://test.org/?utm_source=rss&#038;utm_medium=rss")
        == "http://test.org/"
    )
    assert normalize_url("http://test.org/#partnerid=123") == "http://test.org/"
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
    assert check_url("http://[2001:0db8:85a3:0000:0000:8a2e:0370:7334]") is None
    assert check_url("http://1:2:3:4:5:6:7:8:9") is None


def test_urlcheck_port():
    "Test port handling through check_url."
    assert check_url("http://example.com:80") is not None
    assert check_url("http://example.com:80:80") is None


def test_domain_filter():
    "Test filters related to domain and hostnames."
    assert domain_filter("") is False
    assert domain_filter("a" * 254 + ".com") is False  # exceeds DNS length limit
    d_ok = "a." * 125 + "abc"  # 253 chars — at the DNS length limit
    d_long = "a." * 125 + "abcd"  # 254 chars — over
    assert len(d_ok) == 253 and len(d_long) == 254
    assert domain_filter(d_ok) is True
    assert domain_filter(d_long) is False
    assert domain_filter("too-long" + "g" * 60 + ".org") is False
    assert domain_filter("long" + "g" * 50 + ".org") is True
    assert domain_filter("example.-com") is False
    assert domain_filter("example.") is False
    assert domain_filter("-example.com") is False
    assert domain_filter("_example.com") is False
    assert domain_filter("example.com:") is False
    assert domain_filter("a......b.com") is False
    assert domain_filter("*.example.com") is False
    assert domain_filter("exa-mple.co.uk") is True
    assert domain_filter("kräuter.de") is True
    assert domain_filter("xn--h1aagokeh.xn--p1ai") is True
    assert domain_filter("`$smarty.server.server_name`") is False
    assert domain_filter("$`)}if(a.tryconvertencoding)trycatch(e)const") is False
    assert domain_filter("00x200.jpg,") is False
    assert domain_filter("-100x100.webp") is False
    assert domain_filter("0.gravata.html") is False
    assert domain_filter("https:") is False

    assert domain_filter("127.0.0.1") is True
    assert domain_filter("::1") is True
    assert domain_filter("900.200.100.75") is False
    assert domain_filter("111.111.111") is False
    assert domain_filter("0127.0.0.1") is False

    # hex-only strings that are not IPs must still be validated as domains
    assert domain_filter("abc.de") is True
    assert domain_filter("aced.de") is True
    assert domain_filter("dead.beef") is True

    assert domain_filter("example.jpg") is False
    assert domain_filter("example.html") is False
    assert domain_filter("0.gravatar.com") is False
    assert domain_filter("12345.org") is False
    # assert domain_filter("test.invalidtld") is False


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
    assert extract_domain("https://httpbun.org/") == "httpbun.org"
    assert extract_domain("https://www.httpbun.org/", fast=True) == "httpbun.org"
    assert extract_domain("http://www.mkyong.com.au", fast=True) == "mkyong.com.au"
    assert extract_domain("http://mkyong.t.t.co", fast=True) == "mkyong.t.t.co"
    assert extract_domain("ftp://www4.httpbun.org", fast=True) == "httpbun.org"
    assert extract_domain("http://w3.example.com", fast=True) == "example.com"
    assert extract_domain("https://de.nachrichten.yahoo.com/", fast=True) == "yahoo.com"
    assert (
        extract_domain("http://xn--h1aagokeh.xn--p1ai:8888", fast=True)
        == "xn--h1aagokeh.xn--p1ai"
    )
    assert extract_domain("http://user:pass@domain.test:81", fast=True) == "domain.test"
    assert extract_domain("http://111.2.33.44/test", fast=True) == "111.2.33.44"
    assert (
        extract_domain("http://2001:db8::ff00:42:8329/test", fast=True)
        == "2001:db8::ff00:42:8329"
    )
    assert (
        extract_domain("https://test.xn--0zwm56d.com/", fast=True) == "xn--0zwm56d.com"
    )
    assert extract_domain("http://example.com?query=one", fast=True) == "example.com"
    assert extract_domain("http://example.com#fragment", fast=True) == "example.com"
    # fast-path match yields an empty domain -> falls back to the slow path
    assert extract_domain("http://exam.p@", fast=True) is None
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
    # malformed URLs
    assert is_external("h1234", "https://www.google.co.uk/", ignore_suffix=True) is True


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
            [courlan_bin, "-i", inputfile, "-o", outputfile, "-p", "1"], env=env
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
    _ = _parse("https://example.net/123/abc")

    # urlsplit is only an lru_cache wrapper on some Python versions
    has_urlsplit_cache = hasattr(urlsplit, "cache_info")
    assert langcodes_score.cache_info().currsize > 0
    if has_urlsplit_cache:
        assert urlsplit.cache_info().currsize > 0

    clear_caches()

    assert langcodes_score.cache_info().currsize == 0
    if has_urlsplit_cache:
        assert urlsplit.cache_info().currsize == 0
