"""
Bundles functions needed to target text content and validate the input.
"""


## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import re

from urllib.parse import urlsplit


def typefilter(url):
    '''Make sure the target URL is from a suitable type (HTML page with primarily text)'''
    # directory
    #if url.endswith('/'):
    #    return False
    try:
        # extensions
        if url.endswith(('.atom', '.json', '.css', '.xml', '.js', '.jpg', '.jpeg', '.png', '.gif', '.tiff', '.pdf', '.ogg', '.mp3', '.m4a', '.aac', '.avi', '.mp4', '.mov', '.webm', '.flv', '.ico', '.pls', '.zip', '.tar', '.gz', '.iso', '.swf', '.exe')):
            raise ValueError
        # feeds
        if url.endswith(('/feed', '/rss')):
            raise ValueError
        # navigation
        if re.search(r'/(?:tags?|schlagwort|category|cat|kategorie|kat|auth?or|page|seite|user|search|gallery|gallerie|labels|archives)/', url) or url.endswith('/index'):
            raise ValueError
        # hidden in parameters
        if re.search(r'\.(atom|json|css|xml|js|jpg|jpeg|png|gif|tiff|pdf|ogg|mp3|m4a|aac|avi|mp4|mov|webm|flv|ico|pls|zip|tar|gz|iso|swf)\b', url): # , re.IGNORECASE (?=[&?])
            raise ValueError
        # not suitable
        if re.match('https?://banner.', url) or re.match(r'https?://add?s?\.', url):
            raise ValueError
        if re.search(r'\b(?:doubleclick|tradedoubler|livestream|live|videos?)\b', url):
            raise ValueError
    except ValueError:
        return False
    # default
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
