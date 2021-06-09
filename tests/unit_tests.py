"""
Unit tests for the courlan package.
"""

## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import logging
import os
import sys

from unittest.mock import patch

import pytest

try:
    import tldextract
    TLD_EXTRACTION = tldextract.TLDExtract(suffix_list_urls=None)
except ImportError:
    TLD_EXTRACTION = None

from courlan import clean_url, normalize_url, scrub_url, check_url, is_external, sample_urls, validate_url, extract_links, extract_domain, fix_relative_urls, get_base_url, get_host_and_path, get_hostinfo, is_navigation_page, is_not_crawlable, lang_filter
from courlan.cli import parse_args
from courlan.filters import extension_filter, spam_filter, type_filter


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)



def test_baseurls():
    assert get_base_url('https://example.org/') == 'https://example.org'
    assert get_base_url('https://example.org/test.html?q=test#frag') == 'https://example.org'
    assert get_base_url('example.org') == ''


def test_fix_relative():
    assert fix_relative_urls('https://example.org', 'page.html') == 'https://example.org/page.html'
    assert fix_relative_urls('http://example.org', '//example.org/page.html') == 'http://example.org/page.html'
    assert fix_relative_urls('https://example.org', './page.html') == 'https://example.org/page.html'
    assert fix_relative_urls('https://example.org', '/page.html') == 'https://example.org/page.html'
    # fixing partial URLs
    assert fix_relative_urls('https://example.org', 'https://example.org/test.html') == 'https://example.org/test.html'
    assert fix_relative_urls('https://example.org', '/test.html') == 'https://example.org/test.html'
    assert fix_relative_urls('https://example.org', '//example.org/test.html') == 'https://example.org/test.html'
    assert fix_relative_urls('http://example.org', '//example.org/test.html') == 'http://example.org/test.html'
    assert fix_relative_urls('https://example.org', 'test.html') == 'https://example.org/test.html'
    assert fix_relative_urls('https://example.org', '../../test.html') == 'https://example.org/test.html'


def test_scrub():
    # clean: scrub + normalize
    assert clean_url('ø\xaa') == 'øª'
    # scrub
    assert scrub_url('  https://www.dwds.de') == 'https://www.dwds.de'
    assert scrub_url('<![CDATA[https://www.dwds.de]]>') == 'https://www.dwds.de'
    assert scrub_url('https://www.dwds.de/test?param=test&amp;other=test') == 'https://www.dwds.de/test?param=test&other=test'
    assert scrub_url('https://www.dwds.de/garbledhttps://www.dwds.de/') == 'https://www.dwds.de/garbled'
    assert scrub_url('https://g__https://www.dwds.de/') == 'https://www.dwds.de'
    # exception for archive URLs
    assert scrub_url('https://web.archive.org/web/20131021165347/https://www.imdb.com/') == 'https://web.archive.org/web/20131021165347/https://www.imdb.com'
    # social sharing
    assert scrub_url('https://twitter.com/share?&text=Le%20sabre%20de%20bambou%20%232&via=NouvellesJapon&url=https://nouvellesdujapon.com/le-sabre-de-bambou-2') == 'https://nouvellesdujapon.com/le-sabre-de-bambou-2'
    assert scrub_url('https://www.facebook.com/sharer.php?u=https://nouvellesdujapon.com/le-sabre-de-bambou-2') == 'https://nouvellesdujapon.com/le-sabre-de-bambou-2'
    # end of URL
    #assert scrub_url('https://www.test.com/&') == 'https://www.test.com'


def test_extension_filter():
    assert extension_filter('http://www.example.org/test.js') is False
    assert extension_filter('http://goodbasic.com/GirlInfo.aspx?Pseudo=MilfJanett') is True
    assert extension_filter('https://www.familienrecht-allgaeu.de/de/vermoegensrecht.amp') is True


def test_spam_filter():
    assert spam_filter('http://www.example.org/cams/test.html') is False
    assert spam_filter('http://www.example.org/test.html') is True


def test_type_filter():
    assert type_filter('http://www.example.org/feed') is False
    # straight category
    assert type_filter('http://www.example.org/category/123') is False
    # post simply filed under a category
    assert type_filter('http://www.example.org/category/tropes/time-travel') is True
    assert type_filter('http://www.example.org/test.xml?param=test', strict=True) is False
    assert type_filter('http://www.example.org/test.asp') is True
    assert type_filter('http://ads.example.org/') is False
    # -video- vs. /video/
    assert type_filter('http://my-videos.com/') is True
    assert type_filter('http://my-videos.com/', strict=True) is False
    assert type_filter('http://example.com/video/1') is False
    assert type_filter('http://example.com/new-video-release') is True
    assert type_filter('http://example.com/new-video-release', strict=True) is False


def test_lang_filter():
    assert lang_filter('https://www.20min.ch/fr/story/des-millions-pour-produire-de-l-energie-renouvelable-467974085377', None) is True
    assert lang_filter('https://www.20min.ch/fr/story/des-millions-pour-produire-de-l-energie-renouvelable-467974085377', 'de') is False
    assert lang_filter('https://www.20min.ch/fr/story/des-millions-pour-produire-de-l-energie-renouvelable-467974085377', 'fr') is True
    assert lang_filter('https://www.20min.ch/fr/story/des-millions-pour-produire-de-l-energie-renouvelable-467974085377', 'en') is False
    assert lang_filter('https://www.20min.ch/fr/story/des-millions-pour-produire-de-l-energie-renouvelable-467974085377', 'es') is False


def test_navigation():
    assert is_navigation_page('https://test.org/') is False
    assert is_navigation_page('https://test.org/page/1') is True
    assert is_not_crawlable('https://test.org/login') is True
    assert is_not_crawlable('https://test.org/login/') is True
    assert is_not_crawlable('https://test.org/page') is False


def test_validate():
    assert validate_url('http://www.test[.org/test')[0] is False
    # assert validate_url('http://www.test.org:7ERT/test')[0] is False
    assert validate_url('ntp://www.test.org/test')[0] is False
    assert validate_url('ftps://www.test.org/test')[0] is False
    assert validate_url('http://t.g/test')[0] is False
    assert validate_url('http://test.org/test')[0] is True


def test_normalization():
    assert normalize_url('HTTPS://WWW.DWDS.DE/') == 'https://www.dwds.de/'
    assert normalize_url('http://test.net/foo.html#bar', strict=True) == 'http://test.net/foo.html'
    assert normalize_url('http://test.net/foo.html#bar', strict=False) == 'http://test.net/foo.html#bar'
    assert normalize_url('http://test.net/foo.html#:~:text=night-,vision', strict=True) == 'http://test.net/foo.html'
    assert normalize_url('http://www.example.org:80/test.html') == 'http://www.example.org/test.html'
    assert normalize_url('https://hanxiao.io//404.html') == 'https://hanxiao.io/404.html'


def test_qelems():
    assert normalize_url('http://test.net/foo.html?utm_source=twitter') == 'http://test.net/foo.html?utm_source=twitter'
    assert normalize_url('http://test.net/foo.html?utm_source=twitter', strict=True) == 'http://test.net/foo.html'
    assert normalize_url('http://test.net/foo.html?utm_source=twitter&post=abc&page=2') == 'http://test.net/foo.html?page=2&post=abc&utm_source=twitter'
    assert normalize_url('http://test.net/foo.html?utm_source=twitter&post=abc&page=2', strict=True) == 'http://test.net/foo.html?page=2&post=abc'
    assert normalize_url('http://test.net/foo.html?page=2&itemid=10&lang=en') == 'http://test.net/foo.html?itemid=10&lang=en&page=2'
    with pytest.raises(ValueError):
        assert normalize_url('http://test.net/foo.html?page=2&lang=en', language='de')
        assert normalize_url('http://www.evolanguage.de/index.php?page=deutschkurse_fuer_aerzte&amp;language=ES', language='de')


def test_urlcheck():
    assert check_url('AAA') is None
    assert check_url('1234') is None
    assert check_url('http://ab') is None
    assert check_url('ftps://example.org/') is None
    assert check_url('http://t.g/test') is None
    assert check_url('https://www.dwds.de/test?param=test&amp;other=test', strict=True) == ('https://www.dwds.de/test', 'dwds.de')
    assert check_url('http://example.com/index.html#term', strict=True) is None
    assert check_url('http://example.com/index.html#term', strict=False)[0] == 'http://example.com/index.html#term'
    assert check_url('http://example.com/test.js') is None
    assert check_url('http://twitter.com/') is None
    assert check_url('https://www.httpbin.org/status/200', with_redirects=True) == ('https://www.httpbin.org/status/200', 'httpbin.org')
    #assert check_url('https://www.httpbin.org/status/302', with_redirects=True) == ('https://www.httpbin.org/status/302', 'httpbin.org')
    assert check_url('https://www.httpbin.org/status/404', with_redirects=True) is None
    assert check_url('https://www.ht.or', with_redirects=True) is None
    if TLD_EXTRACTION is None:
        assert check_url('http://www.example') is None
        assert check_url('http://example.invalid/', False) is None
    # recheck type and spam filters
    assert check_url('http://example.org/code/oembed/') is None
    assert check_url('http://cams.com/', strict=False) == ('http://cams.com', 'cams.com')
    assert check_url('http://cams.com/', strict=True) is None
    assert check_url('https://denkiterm.wordpress.com/impressum/', strict=True) is None
    assert check_url('http://www.fischfutter-index.de/improvit-trocken-frostfutter-fur-fast-alle-fische/', strict=True) is not None
    # language and internationalization
    assert check_url('http://example.com/test.html?lang=en', language='de') is None
    assert check_url('http://example.com/test.html?lang=en', language=None) is not None
    assert check_url('http://example.com/test.html?lang=en', language='en') is not None
    assert check_url('http://example.com/de/test.html', language='de') is not None
    assert check_url('http://example.com/en/test.html', language='de') is None
    assert check_url('http://example.com/en/test.html', language=None) is not None
    assert check_url('http://example.com/en/test.html', language='en') is not None
    assert check_url('https://www.myswitzerland.com/de-ch/erlebnisse/veranstaltungen/wild-im-sternen/', language='de') is not None
    assert check_url('https://www.myswitzerland.com/en-id/accommodations/other-types-of-accommodations/on-the-farm/farm-experiences-search/', language='en') is not None
    assert check_url('https://www.myswitzerland.com/EN-ID/accommodations/other-types-of-accommodations/on-the-farm/farm-experiences-search/', language='en') is not None
    # impressum and index
    assert check_url('http://www.example.org/index', strict=True) is None
    assert check_url('http://www.example.org/index.html', strict=True) is None
    assert check_url('http://concordia-hagen.de/impressum.html', strict=True) is None
    assert check_url('http://concordia-hagen.de/de/impressum', strict=True) is None
    assert check_url('http://parkkralle.de/detail/index/sArticle/2704', strict=True) is not None
    assert check_url('https://www.katholisch-in-duisdorf.de/kontakt/links/index.html', strict=True) is not None
    assert check_url('{mylink}') is None


def test_urlutils():
    '''Test URL manipulation tools'''
    assert extract_domain('https://httpbin.org/') == 'httpbin.org'
    assert get_base_url('https://example.org/path') == 'https://example.org'
    assert get_host_and_path('https://example.org/path') == ('https://example.org', '/path')
    assert get_hostinfo('https://example.org/path') == ('example.org', 'https://example.org')
    assert get_hostinfo('https://httpbin.org/') == ('httpbin.org', 'https://httpbin.org')


def test_external():
    '''test domain comparison'''
    assert is_external('https://github.com/', 'https://www.microsoft.com/') is True
    assert is_external('https://microsoft.com/', 'https://www.microsoft.com/', ignore_suffix=True) is False
    assert is_external('https://microsoft.com/', 'https://www.microsoft.com/', ignore_suffix=False) is False
    assert is_external('https://google.com/', 'https://www.google.co.uk/', ignore_suffix=True) is False
    assert is_external('https://google.com/', 'https://www.google.co.uk/', ignore_suffix=False) is True
    # malformed URLs
    assert is_external('h1234', 'https://www.google.co.uk/', ignore_suffix=True) is True
    #if TLD_EXTRACTION is not None:
    #    # tldextract object
    #    tldinfo = TLD_EXTRACTION('http://127.0.0.1:8080/test/')
    #    assert is_external('https://127.0.0.1:80/', tldinfo) is False


def test_extraction():
    '''test link comparison in HTML'''
    assert len(extract_links(None, 'https://test.com/', False)) == 0
    assert len(extract_links('', 'https://test.com/', False)) == 0
    # language
    pagecontent = '<html><a href="https://test.com/example" hreflang="de-DE"/></html>'
    assert len(extract_links(pagecontent, 'https://test.com/', False)) == 1
    assert len(extract_links(pagecontent, 'https://test.com/', True)) == 0
    assert len(extract_links(pagecontent, 'https://test.com/', False, language='de')) == 1
    assert len(extract_links(pagecontent, 'https://test.com/', False, language='en')) == 0
    # x-default
    pagecontent = '<html><a href="https://test.com/example" hreflang="x-default"/></html>'
    assert len(extract_links(pagecontent, 'https://test.com/', False, language='de')) == 1
    assert len(extract_links(pagecontent, 'https://test.com/', False, language='en')) == 1
    # language + content
    pagecontent = '<html><a hreflang="de-DE" href="https://test.com/example"/><a href="https://test.com/example2"/><a href="https://test.com/example2 ADDITIONAL"/></html>'
    links = extract_links(pagecontent, 'https://test.com/', False)
    assert sorted(links) == ['https://test.com/example', 'https://test.com/example2']
    assert len(extract_links(pagecontent, 'https://test.com/', False, language='de')) == 2
    pagecontent = '<html><a hreflang="de-DE" href="https://test.com/example"/><a href="https://test.com/page/2"/></html>'
    assert len(extract_links(pagecontent, 'https://test.com/', False, with_nav=False)) == 1
    assert len(extract_links(pagecontent, 'https://test.com/', False, with_nav=True)) == 2
    pagecontent = "<html><head><title>Links</title></head><body><a href='/links/2/0'>0</a> <a href='/links/2/1'>1</a> </body></html>"
    links = extract_links(pagecontent, 'https://httpbin.org', False, with_nav=True)
    assert sorted(links) == ['https://httpbin.org/links/2/0', 'https://httpbin.org/links/2/1']
    # links undeveloped by CMS
    pagecontent = '<html><a href="{privacy}" target="_privacy">{privacy-link}</a></html>'
    assert len(extract_links(pagecontent, 'https://test.com/', False)) == 0
    assert len(extract_links(pagecontent, 'https://test.com/', True)) == 0


def test_cli():
    '''test the command-line interface'''
    testargs = ['', '-i', 'input.txt', '--outputfile', 'output.txt', '-v', '--language', 'en']
    with patch.object(sys, 'argv', testargs):
        args = parse_args(testargs)
    assert args.inputfile == 'input.txt'
    assert args.outputfile == 'output.txt'
    assert args.verbose is True
    assert args.language == 'en'
    assert os.system('courlan --help') == 0  # exit status


def test_sample():
    '''test URL sampling'''
    assert len(list(sample_urls(['http://test.org/test1', 'http://test.org/test2'], 0))) == 0
    # assert len(sample_urls(['http://test.org/test1', 'http://test.org/test2'], 1)) == 1
    mylist = ['http://t.o/t1', 'http://test.org/test1', 'http://test.org/test2', 'http://test2.org/test2']
    assert len(list(sample_urls(mylist, 1, verbose=True))) == 1
    assert len(list(sample_urls(mylist, 1, exclude_min=10, verbose=True))) == 0
    assert len(list(sample_urls(mylist, 1, exclude_max=1, verbose=True))) == 0


def test_examples():
    '''test README examples'''
    assert check_url('https://github.com/adbar/courlan') == ('https://github.com/adbar/courlan', 'github.com')
    assert check_url('https://httpbin.org/redirect-to?url=http%3A%2F%2Fexample.org', strict=True) == ('https://httpbin.org/redirect-to', 'httpbin.org')
    assert clean_url('HTTPS://WWW.DWDS.DE:80/') == 'https://www.dwds.de'
    assert validate_url('http://1234') == (False, None)
    assert validate_url('http://www.example.org/')[0] is True
    assert normalize_url('http://test.net/foo.html?utm_source=twitter&post=abc&page=2#fragment', strict=True) == 'http://test.net/foo.html?page=2&post=abc'
