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

from courlan.clean import clean_url, normalize_url, scrub_url
from courlan.cli import parse_args
from courlan.core import check_url, sample_urls, validate_url
from courlan.filters import extension_filter, spam_filter, type_filter

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


def test_scrub():
    assert scrub_url('  https://www.dwds.de') == 'https://www.dwds.de'
    assert scrub_url('<![CDATA[https://www.dwds.de]]>') == 'https://www.dwds.de'
    assert scrub_url('https://www.dwds.de/test?param=test&amp;other=test') == 'https://www.dwds.de/test?param=test&other=test'
    assert scrub_url('https://www.dwds.de/garbledhttps://www.dwds.de/') == 'https://www.dwds.de'
    # exception for archive URLs
    assert scrub_url('https://web.archive.org/web/20131021165347/https://www.imdb.com/') == 'https://web.archive.org/web/20131021165347/https://www.imdb.com'


def test_extension_filter():
    assert extension_filter('http://www.example.org/test.js') is False
    assert extension_filter('http://goodbasic.com/GirlInfo.aspx?Pseudo=MilfJanett') is True
    assert extension_filter('https://www.familienrecht-allgaeu.de/de/vermoegensrecht.amp') is True


def test_spam_filter():
    assert spam_filter('http://www.example.org/cams/test.html') is False
    assert spam_filter('http://www.example.org/test.html') is True


def test_type_filter():
    assert type_filter('http://www.example.org/feed') is False
    assert type_filter('http://www.example.org/category/123') is False
    assert type_filter('http://www.example.org/test.xml?param=test', strict=True) is False
    assert type_filter('http://www.example.org/test.asp') is True
    assert type_filter('http://ads.example.org/') is False
    assert type_filter('http://my-videos.com/') is False
    assert type_filter('http://www.example.org/index', strict=True) is False
    assert type_filter('http://www.example.org/index.html', strict=True) is False
    assert type_filter('http://concordia-hagen.de/impressum.html', strict=True) is False
    assert type_filter('http://parkkralle.de/detail/index/sArticle/2704', strict=True) is True
    assert type_filter('https://www.katholisch-in-duisdorf.de/kontakt/links/index.html', strict=True) is True


def test_validate():
    assert validate_url('http://www.test[.org/test')[0] is False
    # assert validate_url('http://www.test.org:7ERT/test')[0] is False
    assert validate_url('ntp://www.test.org/test')[0] is False
    assert validate_url('ftps://www.test.org/test')[0] is False
    assert validate_url('http://t.g/test')[0] is False
    assert validate_url('http://test.org/test')[0] is True


def test_normalization():
    assert normalize_url('HTTPS://WWW.DWDS.DE/') == 'https://www.dwds.de/'
    assert normalize_url('http://test.net/foo.html#bar') == 'http://test.net/foo.html'
    assert normalize_url('http://test.net/foo.html#:~:text=night-,vision') == 'http://test.net/foo.html'
    assert normalize_url('http://www.example.org:80/test.html') == 'http://www.example.org/test.html'


def test_qelems():
    assert normalize_url('http://test.net/foo.html?utm_source=twitter') == 'http://test.net/foo.html?utm_source=twitter'
    assert normalize_url('http://test.net/foo.html?utm_source=twitter', strict=True) == 'http://test.net/foo.html'
    assert normalize_url('http://test.net/foo.html?utm_source=twitter&post=abc&page=2') == 'http://test.net/foo.html?page=2&post=abc&utm_source=twitter'
    assert normalize_url('http://test.net/foo.html?utm_source=twitter&post=abc&page=2', strict=True) == 'http://test.net/foo.html?page=2&post=abc'
    assert normalize_url('http://test.net/foo.html?page=2&itemid=10&lang=en') == 'http://test.net/foo.html?itemid=10&lang=en&page=2'
    with pytest.raises(ValueError):
        assert normalize_url('http://test.net/foo.html?page=2&lang=en', with_language=True)
        assert normalize_url('http://www.evolanguage.de/index.php?page=deutschkurse_fuer_aerzte&amp;language=ES', with_language=True)


def test_urlcheck():
    assert check_url('AAA') is None
    assert check_url('1234') is None
    assert check_url('http://ab') is None
    assert check_url('ftps://example.org/') is None
    assert check_url('http://t.g/test') is None
    assert check_url('https://www.dwds.de/test?param=test&amp;other=test', strict=True) == ('https://www.dwds.de/test', 'dwds.de')
    assert check_url('http://example.com/index.html#term')[0] == 'http://example.com/index.html'
    assert check_url('http://example.com/test.js') is None
    assert check_url('http://example.com/test.html?lang=en', with_language=True) is None
    assert check_url('http://example.com/test.html?lang=en', with_language=False) is not None
    assert check_url('http://twitter.com/') is None
    # assert urlcheck('http://example.invalid/', False) is None
    assert check_url('https://www.httpbin.org/status/200', with_redirects=True) == ('https://www.httpbin.org/status/200', 'httpbin.org')
    assert check_url('https://www.httpbin.org/status/404', with_redirects=True) is None
    assert check_url('https://www.ht.or', with_redirects=True) is None
    assert check_url('http://www.example') is not None
    # recheck type and spam filters
    assert check_url('http://example.org/code/oembed/') is None
    assert check_url('http://cams.com/') is None
    assert check_url('https://denkiterm.wordpress.com/impressum/', strict=True) is None
    assert check_url('http://www.fischfutter-index.de/improvit-trocken-frostfutter-fur-fast-alle-fische/', strict=True) is not None


def test_cli():
    '''test the command-line interface'''
    testargs = ['', '-i', 'input.txt', '--outputfile', 'output.txt', '-v']
    with patch.object(sys, 'argv', testargs):
        args = parse_args(testargs)
    assert args.inputfile == 'input.txt'
    assert args.outputfile == 'output.txt'
    assert args.verbose is True
    assert os.system('courlan --help') == 0  # exit status


def test_sample():
    assert len(list(sample_urls(['http://test.org/test1', 'http://test.org/test2'], 0))) == 0
    # assert len(sample_urls(['http://test.org/test1', 'http://test.org/test2'], 1)) == 1
    mylist = ['http://t.o/t1', 'http://test.org/test1', 'http://test.org/test2', 'http://test2.org/test2']
    assert len(list(sample_urls(mylist, 1, verbose=True))) == 1
    assert len(list(sample_urls(mylist, 1, exclude_min=10, verbose=True))) == 0
    assert len(list(sample_urls(mylist, 1, exclude_max=1, verbose=True))) == 0


def test_examples():
    '''Test README examples'''
    assert check_url('https://github.com/adbar/courlan') == ('https://github.com/adbar/courlan', 'github.com')
    assert check_url('https://httpbin.org/redirect-to?url=http%3A%2F%2Fexample.org', strict=True) == ('https://httpbin.org/redirect-to', 'httpbin.org')
    assert clean_url('HTTPS://WWW.DWDS.DE:80/') == 'https://www.dwds.de'
    assert validate_url('http://1234') == (False, None)
    assert validate_url('http://www.example.org/')[0] is True
    assert normalize_url('http://test.net/foo.html?utm_source=twitter&post=abc&page=2#fragment', strict=True) == 'http://test.net/foo.html?page=2&post=abc'
