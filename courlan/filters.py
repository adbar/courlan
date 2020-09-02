"""
Bundles functions needed to target text content and validate the input.
"""


## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import re

from urllib.parse import urlparse


WORDPRESS_FILTER = re.compile(r'/(?:tags?|schlagwort|category|cat|kategorie|kat|auth?or|page|seite|user|search|gallery|gall?erie|labels|archives|uploads|modules|attachment)/', re.IGNORECASE)
PARAM_FILTER = re.compile(r'\.(atom|json|css|xml|js|jpg|jpeg|png|gif|tiff|pdf|ogg|mp3|m4a|aac|avi|mp4|mov|webm|flv|ico|pls|zip|tar|gz|iso|swf)\b', re.IGNORECASE)  # , re.IGNORECASE (?=[&?])
PATH_FILTER = re.compile(r'\.[a-z]{2,5}/(impressum|index)(\.html?|\.php)?$', re.IGNORECASE)
ADULT_FILTER = re.compile(r'\b(?:adult|amateur|cams?|gangbang|incest|sexyeroti[ck]|sexcam|bild\-?kontakte)\b|\b(?:arsch|fick|porno?)|(?:cash|swinger)\b', re.IGNORECASE)


def basic_filter(url):
    '''Filter URLs based on basic formal characteristics'''
    if not url.startswith('http') or len(url) >= 500 or len(url) < 10:
        return False
    return True


def extension_filter(component):
    '''Filter based on file extension'''
    if re.search(r'\.[a-z]{2,5}$', component) and not component.endswith(('.amp', '.asp', '.aspx', '.cfm', '.cgi', '.htm', 'html', '.jsp', '.php', '.pl')):
        return False
    return True


def spam_filter(url):
    '''Try to filter out spam and adult websites'''
    # TODO: to improve!
    #for exp in (''):
    #    if exp in url:
    #        return False
    if ADULT_FILTER.search(url):
    #  or re.search(r'\b(?:sex)\b', url): # live|xxx|sex|ass|orgasm|cams|
        return False
    # default
    return True


def type_filter(url, strict=False):
    '''Make sure the target URL is from a suitable type (HTML page with primarily text)'''
    # directory
    #if url.endswith('/'):
    #    return False
    try:
        # feeds
        if url.endswith(('/feed', '/rss')):
            raise ValueError
        # embedded content
        if re.search(r'/oembed\b', url, re.IGNORECASE):
            raise ValueError
        # wordpress structure
        if WORDPRESS_FILTER.search(url):
            raise ValueError
        # hidden in parameters
        if strict is True and PARAM_FILTER.search(url):
            raise ValueError
        # not suitable
        if re.match(r'https?://banner\.|https?://add?s?\.', url, re.IGNORECASE):
            raise ValueError
        if re.search(r'\b(?:doubleclick|tradedoubler|livestream|live|videos?)\b', url, re.IGNORECASE):
            raise ValueError
        # strict content filtering
        if strict is True and PATH_FILTER.search(url):
            raise ValueError
    except ValueError:
        return False
    # default
    return True


def validate_url(url):
    '''Parse and validate the input'''
    try:
        parsed_url = urlparse(url)
    except ValueError:
        return False, None
    if bool(parsed_url.scheme) is False or parsed_url.scheme not in ('http', 'https'):
        return False, None
    if len(parsed_url.netloc) < 5 or \
       (parsed_url.netloc.startswith('www.') and len(parsed_url.netloc) < 8):
        return False, None
    # if validators.url(parsed_url.geturl(), public=True) is False:
    #    return False
    # default
    return True, parsed_url
