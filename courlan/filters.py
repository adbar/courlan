"""
Bundles functions needed to target text content and validate the input.
"""


## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import re

from urllib.parse import urlsplit


def typefilter(url, strict=False):
    '''Make sure the target URL is from a suitable type (HTML page with primarily text)'''
    # directory
    #if url.endswith('/'):
    #    return False
    try:
        # feeds
        if url.endswith(('/feed', '/rss')):
            raise ValueError
        # embedded content
        if re.search(r'/oembed\b', url):
            raise ValueError
        # wordpress structure
        if re.search(r'/(?:tags?|schlagwort|category|cat|kategorie|kat|auth?or|page|seite|user|search|gallery|gallerie|labels|archives|uploads|modules|attachment)/', url):
            raise ValueError
        # hidden in parameters
        if strict is True and re.search(r'\.(atom|json|css|xml|js|jpg|jpeg|png|gif|tiff|pdf|ogg|mp3|m4a|aac|avi|mp4|mov|webm|flv|ico|pls|zip|tar|gz|iso|swf)\b', url): # , re.IGNORECASE (?=[&?])
            raise ValueError
        # not suitable
        if re.match('https?://banner.', url) or re.match(r'https?://add?s?\.', url):
            raise ValueError
        if re.search(r'\b(?:doubleclick|tradedoubler|livestream|live|videos?)\b', url):
            raise ValueError
        # strict content filtering
        if strict is True and re.search(r'(impressum|index)(\.html)?', url):
            raise ValueError
    except ValueError:
        return False
    # default
    return True


def extensionfilter(component):
    '''Filter based on file extension'''
    if re.search(r'https?://.+?/.+?\.[a-z]{2,5}$', component) and not component.endswith(('html', '.htm', '.asp', '.php', '.jsp', '.pl', '.cgi', '.cfm')):
        return False
    return True


def spamfilter(url):
    '''Try to filter out spam and adult websites'''
    # TODO: to improve!
    #for exp in (''):
    #    if exp in url:
    #        return False
    if re.search(r'\b(?:adult|amateur|cams?|gangbang|incest|sexyeroti[ck]|sexcam|bild\-?kontakte)\b', url) or re.search(r'\b(?:arsch|fick|porno?)', url) or re.search(r'(?:cash|swinger)\b', url):
    #  or re.search(r'\b(?:sex)\b', url): # live|xxx|sex|ass|orgasm|cams|
        return False
    # default
    return True


def validate_url(url):
    '''Parse and validate the input'''
    parsed_url = urlsplit(url) # was urlparse(url)
    if bool(parsed_url.scheme) is False or len(parsed_url.netloc) < 4:
        return False, None
    if parsed_url.scheme not in ('http', 'https'):
        return False, None
    # if validators.url(parsed_url.geturl(), public=True) is False:
    #    return False
    # default
    return True, parsed_url
