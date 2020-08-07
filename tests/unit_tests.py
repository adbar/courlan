
from urllib.parse import urlsplit

from urltools.clean import clean
from urltools.core import urlcheck, validate
from urltools.filters import spamfilter, typefilter


def test_clean():
    assert clean('  https://www.dwds.de') == 'https://www.dwds.de'
    assert clean('HTTPS://WWW.DWDS.DE/') == 'https://www.dwds.de'
    assert clean('<![CDATA[https://www.dwds.de]]>') == 'https://www.dwds.de'
    assert clean('https://www.dwds.de/test?param=test&amp;other=test') == 'https://www.dwds.de/test?param=test&other=test'
    assert clean('https://www.dwds.de/garbledhttps://www.dwds.de/') == 'https://www.dwds.de'


def test_spamfilter():
    assert spamfilter('http://www.example.org/cams/test.html') is False
    assert spamfilter('http://www.example.org/test.html') is True


def test_typefilter():
    assert typefilter('http://www.example.org/test.js') is False
    assert typefilter('http://www.example.org/feed') is False
    assert typefilter('http://www.example.org/category/123') is False
    assert typefilter('http://www.example.org/test.xml?param=test') is False
    assert typefilter('http://www.example.org/test.asp') is True


def test_validate():
    assert validate(urlsplit('ftp://www.test.org/test')) is False
    assert validate(urlsplit('http://t.g/test')) is False
    assert validate(urlsplit('http://test.org/test')) is True


def test_urlcheck():
    assert urlcheck('AAA', False) is None
    assert urlcheck('http://ab', False) is None
    assert urlcheck('https://www.dwds.de/test?param=test&amp;other=test', False) == ('https://www.dwds.de/test', 'dwds.de')