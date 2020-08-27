## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license


from urllib.parse import urlsplit

from courlan.clean import clean_url
from courlan.core import sample_urls, urlcheck, validate
from courlan.filters import spamfilter, typefilter


def test_clean():
    assert clean_url('  https://www.dwds.de') == 'https://www.dwds.de'
    assert clean_url('HTTPS://WWW.DWDS.DE/') == 'https://www.dwds.de'
    assert clean_url('<![CDATA[https://www.dwds.de]]>') == 'https://www.dwds.de'
    assert clean_url('https://www.dwds.de/test?param=test&amp;other=test') == 'https://www.dwds.de/test?param=test&other=test'
    assert clean_url('https://www.dwds.de/garbledhttps://www.dwds.de/') == 'https://www.dwds.de'


def test_spamfilter():
    assert spamfilter('http://www.example.org/cams/test.html') is False
    assert spamfilter('http://www.example.org/test.html') is True


def test_typefilter():
    assert typefilter('http://www.example.org/test.js') is False
    assert typefilter('http://www.example.org/feed') is False
    assert typefilter('http://www.example.org/category/123') is False
    assert typefilter('http://www.example.org/test.xml?param=test') is False
    assert typefilter('http://www.example.org/test.asp') is True
    assert typefilter('http://ads.example.org/') is False
    assert typefilter('http://my-videos.com/') is False


def test_validate():
    assert validate(urlsplit('ntp://www.test.org/test')) is False
    assert validate(urlsplit('ftps://www.test.org/test')) is False
    assert validate(urlsplit('http://t.g/test')) is False
    assert validate(urlsplit('http://test.org/test')) is True


def test_urlcheck():
    assert urlcheck('AAA') is None
    assert urlcheck('http://ab') is None
    assert urlcheck('ftps://example.org/') is None
    assert urlcheck('https://www.dwds.de/test?param=test&amp;other=test') == ('https://www.dwds.de/test', 'dwds.de')
    assert urlcheck('http://example.com/index.html#term')[0] == 'http://example.com/index.html'
    assert urlcheck('http://example.com/test.js') is None
    assert urlcheck('http://example.com/test.html?lang=en') is None
    assert urlcheck('http://twitter.com/') is None
    # assert urlcheck('http://example.invalid/', False) is None
    assert urlcheck('https://www.httpbin.org/status/200', with_redirects=True) == ('https://www.httpbin.org/status/200', 'httpbin.org')


def test_sample():
    # assert len(sample_urls(['http://test.org/test1', 'http://test.org/test2'], 1)) == 1
    assert len(sample_urls(['http://test.org/test1', 'http://test.org/test2', 'http://test2.org/test2'], 1)) == 1

