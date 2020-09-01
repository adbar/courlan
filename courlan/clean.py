"""
Functions performing URL trimming and cleaning
"""

## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import logging
import re

from urllib.parse import parse_qs, urlencode, urlparse, ParseResult

from .settings import ALLOWED_PARAMS, CONTROL_PARAMS, TARGET_LANG


def clean_url(url):
    '''Strip unnecessary parts and make sure only one URL is considered'''
    # trim
    url = url.strip()
    # clean the input string
    url = url.replace('[ \t]+', '')
    # trailing slashes
    url = url.rstrip('/')
    # CDATA             # <![CDATA[http://www.urbanlife.de/item/260-bmw-i8-hybrid-revolution-unter-den-sportwagen.html]]>
    if url.startswith('<![CDATA['): # re.match(r'<!\[CDATA\[', url):
        url = url.replace('<![CDATA[', '') # url = re.sub(r'^<!\[CDATA\[', '', url)
        url = url.replace(']]>', '') # url = re.sub(r'\]\]>$', '', url)
    # &amp;
    if '&amp;' in url:
        url = url.replace('&amp;', '&')
    # double/faulty URLs
    protocols = re.findall(r'https?://', url)
    if len(protocols) > 1 and not 'web.archive.org' in url:
        logging.debug('double url: %s %s', len(protocols), url)
        match = re.match(r'https?://.+?(https?://.+?)(?:https?://|$)', url)
        if match:
            url = match.group(1)
            logging.debug('taking url: %s', url)
    # lower
    url = url.lower()
    return url


def clean_query(parsed_url, with_language=False):
    '''Strip unwanted query elements'''
    if len(parsed_url.query) > 0:
        qdict = parse_qs(parsed_url.query)
        del_elems = []
        for qelem in qdict:
            teststr = qelem.lower()
            if teststr not in ALLOWED_PARAMS and teststr not in CONTROL_PARAMS:
                del_elems.append(qelem)
            # control language
            elif teststr in CONTROL_PARAMS and with_language is True:
                if teststr.lower() not in TARGET_LANG:
                    logging.debug('bad lang: %s %s', qelem, qdict[qelem])
                    raise ValueError
        for elem in del_elems:
            del qdict[elem]
        newstring = urlencode(qdict, doseq=True)
        parsed_url = parsed_url._replace(query=newstring)
    return parsed_url


def normalize_url(parsed_url, with_language=False):
    '''Takes a URL string or a parsed URL and returns a (basically) normalized URL string'''
    if not isinstance(parsed_url, ParseResult):
        parsed_url = urlparse(parsed_url)
    # port
    if parsed_url.port is not None and parsed_url.port in (80, 443):
        parsed_url = parsed_url._replace(port=None)
    # lowercase + remove fragments
    parsed_url = parsed_url._replace(
                 scheme=parsed_url.scheme.lower(),
                 netloc=parsed_url.netloc.lower(),
                 fragment=''
                 )
    # strip unwanted query elements
    parsed_url = clean_query(parsed_url, with_language)
    # rebuild
    return parsed_url.geturl()
