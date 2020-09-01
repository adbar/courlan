"""
Core functions needed to make the module work.
"""

## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

#import locale
import logging
import re
import sys

#from functools import cmp_to_key
from random import sample

import tldextract

from .clean import normalize_url, scrub_url
from .filters import basic_filter, extension_filter, spam_filter, type_filter, validate_url
from .network import redirection_test
from .settings import BLACKLIST


LOGGER = logging.getLogger(__name__)

# extract callable that falls back to the included TLD snapshot, no live HTTP fetching
TLD_EXTRACTION = tldextract.TLDExtract(suffix_list_urls=None)


def extract_domain(url):
    '''Extract domain name information using top-level domain info'''
    tldinfo = TLD_EXTRACTION(url)
    # domain TLD blacklist
    if tldinfo.domain in BLACKLIST:
        return None
    # return domain
    return re.sub(r'^www[0-9]*\.', '', '.'.join(part for part in tldinfo if part))


def check_url(url, strict=False, with_redirects=False, with_language=False):
    """ Check links for appropriateness and sanity
    Args:
        url: url to check
        redbool: switch for redirection test

    Returns:
        A tuple consisting of canonical URL and extracted domain

    Raises:
        ValueError, handled in exception.
    """

    # first sanity check
    # use standard parsing library, validate and strip fragments, then normalize
    try:
        # length test
        if basic_filter(url) is False:
            raise ValueError

        # clean
        url = scrub_url(url)

        # get potential redirect
        if with_redirects is True:
            url = redirection_test(url)
            if url is None:
                raise ValueError

        # spam
        if spam_filter(url) is False:
            raise ValueError
        # structural elements
        if type_filter(url, strict) is False:
            raise ValueError

        # split and validate
        validation_test, parsed_url = validate_url(url)
        if validation_test is False:
            raise ValueError

        # content filter based on extensions
        if extension_filter(parsed_url.path) is False:
            raise ValueError

        # normalize
        url = normalize_url(parsed_url, strict, with_language)

    # handle exceptions
    except (AttributeError, ValueError, UnicodeError):
        # LOGGER.debug('discarded URL: %s', url)
        return None

    # domain info
    domain = extract_domain(url)
    if domain is None:
        return None

    return (url, domain)


def sample_urls(urllist, samplesize, exclude_min=None, exclude_max=None, strict=False, verbose=False):
    '''Sample a list of URLs by domain name, optionally using constraints on their number'''
    lastseen, urlbuffer = None, set()
    if verbose is True:
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
    for url in sorted(urllist): # key=cmp_to_key(locale.strcoll)
        # first basic filter
        checked = check_url(url, strict=strict, with_redirects=False)
        if checked is None:
            continue
        url, domain = checked[0], checked[1]
        # continue collection
        if domain == lastseen:
            urlbuffer.add(url)
        # sample, drop, fresh start
        else:
            # threshold for too small websites
            if exclude_min is None or len(urlbuffer) >= exclude_min:
                # write all the buffer
                if len(urlbuffer) <= samplesize:
                    yield from sorted(urlbuffer)
                    LOGGER.info('%s\t\turls: %s', lastseen, len(urlbuffer))
                # or sample URLs
                else:
                    # threshold for too large websites
                    if exclude_max is None or len(urlbuffer) <= exclude_max:
                        yield from sorted(sample(urlbuffer, samplesize))
                        LOGGER.info('%s\t\turls: %s\tprop.: %s', lastseen, len(urlbuffer), samplesize/len(urlbuffer))
                    else:
                        LOGGER.info('discarded (exclude size): %s\t\turls: %s', lastseen, len(urlbuffer))
            else:
                LOGGER.info('discarded (exclude size): %s\t\turls: %s', lastseen, len(urlbuffer))
            urlbuffer = set()
            urlbuffer.add(url)
        lastseen = domain
