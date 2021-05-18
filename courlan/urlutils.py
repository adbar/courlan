"""
Functions related to URL manipulation.
"""

import re

from urllib.parse import urlparse


def get_base_url(url):
    'Strip URL of some of its parts to get base URL.'
    parsed_url = urlparse(url)
    return parsed_url._replace(path='', params='', query='', fragment='').geturl()


def fix_relative_urls(baseurl, url):
    'Prepend protocol and host information to relative links.'
    if url.startswith('//'):
        if baseurl.startswith('https'):
            urlfix = 'https:' + url
        else:
            urlfix = 'http:' + url
    elif url.startswith('/'):
        urlfix = baseurl + url
    # imperfect path handling
    elif url.startswith('.'):
        urlfix = baseurl + '/' + re.sub(r'(.+/)+', '', url)
    elif not url.startswith('http'):
        urlfix = baseurl + '/' + url
    else:
        urlfix = url
    return urlfix
