"""
Functions performing URL trimming and cleaning
"""

## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import logging
import re

from collections import OrderedDict
from urllib.parse import parse_qs, urlencode, urlparse, ParseResult

from .filters import validate_url
from .settings import ALLOWED_PARAMS, CONTROL_PARAMS,\
                      TARGET_LANG_DE, TARGET_LANG_EN


PROTOCOLS = re.compile(r'https?://')
SELECTION = re.compile(r'(https?://[^">&? ]+?)(?:https?://)|(?:https?://[^/]+?/[^/]+?[&?]u(rl)?=)(https?://[^"> ]+)')
MIDDLE_URL = re.compile(r'https?://.+?(https?://.+?)(?:https?://|$)')

NETLOC_RE = re.compile(r'(?<=\w):(?:80|443)')
PATH1 = re.compile(r'/+')
PATH2 = re.compile(r'^(?:/\.\.(?![^/]))+')


def clean_url(url, language=None):
    '''Helper function: chained scrubbing and normalization'''
    try:
        return normalize_url(scrub_url(url), language)
    except (AttributeError, ValueError):
        return None


def scrub_url(url):
    '''Strip unnecessary parts and make sure only one URL is considered'''
    # trim
    # https://github.com/cocrawler/cocrawler/blob/main/cocrawler/urls.py
    # remove leading and trailing white space and unescaped control chars
    url = url.strip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
                    '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f \r\n')
    # clean the input string
    url = url.replace('[ \t]+', '')
    # <![CDATA[http://www.urbanlife.de/item/260-bmw-i8-hybrid-revolution-unter-den-sportwagen.html]]>
    if url.startswith('<![CDATA['): # re.match(r'<!\[CDATA\[', url):
        url = url.replace('<![CDATA[', '') # url = re.sub(r'^<!\[CDATA\[', '', url)
        url = url.replace(']]>', '') # url = re.sub(r'\]\]>$', '', url)
    # markup rests
    url = re.sub(r'</?a>', '', url)
    # &amp;
    if '&amp;' in url:
        url = url.replace('&amp;', '&')
    #if '"' in link:
    #    link = link.split('"')[0]
    # double/faulty URLs
    protocols = PROTOCOLS.findall(url)
    if len(protocols) > 1 and not 'web.archive.org' in url:
        logging.debug('double url: %s %s', len(protocols), url)
        match = SELECTION.match(url)
        if match and validate_url(match.group(1))[0] is True:
            url = match.group(1)
            logging.debug('taking url: %s', url)
        else:
            match = MIDDLE_URL.match(url)
            if match and validate_url(match.group(1))[0] is True:
                url = match.group(1)
                logging.debug('taking url: %s', url)
    # too long and garbled URLs e.g. due to quotes URLs
    # https://github.com/cocrawler/cocrawler/blob/main/cocrawler/urls.py
    if len(url) > 500:  # arbitrary choice
        match = re.match(r'(.*?)[<>"\'\r\n ]', url)
        if match:
            url = match.group(1)
        if len(url) > 500:
            logging.debug('invalid-looking link %s of length %d',
                           url[:50] + '...', len(url))
    # trailing ampersand
    url = url.strip('&')
    # trailing slashes in URLs without path or in embedded URLs
    if url.count('/') == 3 or url.count('://') > 1:
        url = url.rstrip('/')
    # lower
    # url = url.lower()
    return url


def clean_query(parsed_url, strict=False, language=None):
    '''Strip unwanted query elements'''
    if len(parsed_url.query) > 0:
        qdict = parse_qs(parsed_url.query)
        newqdict = OrderedDict()
        for qelem in sorted(qdict.keys()):
            teststr = qelem.lower()
            # control param
            if strict is True and \
               teststr not in ALLOWED_PARAMS and teststr not in CONTROL_PARAMS:
                continue
            # control language
            if language is not None and teststr in CONTROL_PARAMS:
                found_lang = str(qdict[qelem][0])
                if (language == 'de' and found_lang not in TARGET_LANG_DE) or \
                   (language == 'en' and found_lang not in TARGET_LANG_EN) or \
                   found_lang != language:
                    logging.debug('bad lang: %s %s %s', language, qelem, found_lang)
                    raise ValueError
            # insert
            newqdict[qelem] = qdict[qelem]
        newstring = urlencode(newqdict, doseq=True)
        parsed_url = parsed_url._replace(query=newstring)
    return parsed_url


def normalize_url(parsed_url, strict=False, language=None):
    '''Takes a URL string or a parsed URL and returns a (basically) normalized URL string'''
    if not isinstance(parsed_url, ParseResult):
        parsed_url = urlparse(parsed_url)
    # port
    if parsed_url.port is not None and parsed_url.port in (80, 443):
        parsed_url = parsed_url._replace(netloc=NETLOC_RE.sub('', parsed_url.netloc))
    # path: https://github.com/saintamh/alcazar/blob/master/alcazar/utils/urls.py
    newpath = PATH1.sub('/', parsed_url.path)
    # Leading /../'s in the path are removed
    newpath = PATH2.sub('', newpath)
    # fragment
    if strict is True:
        newfragment = ''
    else:
        newfragment = parsed_url.fragment
    # lowercase + remove fragments
    parsed_url = parsed_url._replace(
                 scheme=parsed_url.scheme.lower(),
                 netloc=parsed_url.netloc.lower(),
                 path=newpath,
                 fragment=newfragment
                 )
    # strip unwanted query elements
    parsed_url = clean_query(parsed_url, strict, language)
    # rebuild
    return parsed_url.geturl()
