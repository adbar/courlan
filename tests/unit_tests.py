

from urllib.parse import urlsplit

from urltools.clean import clean
from urltools.core import validate
from urltools.filters import spamfilter, typefilter


def test_clean():
    assert clean('HTTPS://WWW.DWDS.DE/') == 'https://www.dwds.de'


def test_filters():
    assert spamfilter('http://www.example.org/cams/test.html') is False
    assert typefilter('http://www.example.org/test.js') is False


def test_validate():
    assert validate(urlsplit('ftp://www.test.org/test')) is False
    assert validate(urlsplit('http://t.g/test')) is False
    assert validate(urlsplit('http://test.org/test')) is True