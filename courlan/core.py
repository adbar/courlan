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


from .clean import normalize_url, scrub_url
from .compatibility import TLD_EXTRACTION
from .filters import basic_filter, extension_filter, lang_filter, \
                     PATH_FILTER, spam_filter, type_filter, validate_url
from .network import redirection_test
from .settings import BLACKLIST
from .urlutils import extract_domain, fix_relative_urls, is_external


LOGGER = logging.getLogger(__name__)

FIND_LINKS_REGEX = re.compile(r'<a [^<>]+?>', re.I)
HREFLANG_REGEX = re.compile(r'hreflang=["\']([a-z-]+)', re.I)
LINK_REGEX = re.compile(r'href=["\']([^ ]+?)["\']', re.I)


def check_url(url, strict=False, with_redirects=False, language=None, with_nav=False):
    """ Check links for appropriateness and sanity
    Args:
        url: url to check
        strict: set to True for stricter filtering
        with_redirects: set to True for redirection test (per HTTP HEAD request)
        language: set target language (ISO 639-1 codes)
        with_nav: set to True to include navigation pages instead of discarding them

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
        if strict is True and spam_filter(url) is False:
            raise ValueError
        # structural elements
        if type_filter(url, strict=strict, with_nav=with_nav) is False:
            raise ValueError

        # split and validate
        validation_test, parsed_url = validate_url(url)
        if validation_test is False:
            raise ValueError

        # content filter based on extensions
        if extension_filter(parsed_url.path) is False:
            raise ValueError

        # strict content filtering
        if strict is True and PATH_FILTER.match(parsed_url.path):
            raise ValueError

        # internationalization in URL
        if lang_filter(parsed_url.path, language) is False:
            raise ValueError

        # normalize
        url = normalize_url(parsed_url, strict, language)

    # handle exceptions
    except (AttributeError, ValueError, UnicodeError):
        # LOGGER.debug('discarded URL: %s', url)
        return None

    # domain info
    domain = extract_domain(url, blacklist=BLACKLIST)
    if domain is None:
        return None

    return url, domain


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


def extract_links(pagecontent, base_url, external_bool, language=None,
                  strict=True, with_nav=False, redirects=False, reference=None):
    """ Filter links in a HTML document using a series of heuristics
    Args:
        pagecontent: whole page in binary format
        base_url: beginning of the URL, without path, fragment and query
        external: set to True for external links only, False for
                  internal links only
        language: set target language (ISO 639-1 codes)
        strict: set to True for stricter filtering
        with_nav: set to True to include navigation pages instead of discarding them
        with_redirects: set to True for redirection test (per HTTP HEAD request)
        reference: provide a host reference for external/internal evaluation

    Returns:
        A set containing filtered HTTP links checked for sanity and consistency.

    Raises:
        Nothing.
    """
    candidates, validlinks = set(), set()
    if pagecontent is None or pagecontent == '':
        return validlinks
    # define host reference
    if reference is None:
        if TLD_EXTRACTION is not None:
            reference = TLD_EXTRACTION(base_url)
        else:
            reference = base_url
    # extract links
    for link in FIND_LINKS_REGEX.findall(pagecontent):
        # https://en.wikipedia.org/wiki/Hreflang
        if language is not None and 'hreflang' in link:
            langmatch = HREFLANG_REGEX.search(link)
            if langmatch and (
                langmatch.group(1).startswith(language) or
                langmatch.group(1) == 'x-default'
                ):
                mymatch = LINK_REGEX.search(link)
                if mymatch:
                    candidates.add(mymatch.group(1))
        # default
        else:
            mymatch = LINK_REGEX.search(link)
            if mymatch:
                candidates.add(mymatch.group(1))
    # filter candidates
    for link in candidates:
        # repair using base
        if not link.startswith('http'):
            link = fix_relative_urls(base_url, link)
        # check
        checked = check_url(link, strict=strict, with_nav=with_nav,
                            with_redirects=redirects, language=language)
        if checked is None:
            continue
        # additional cleaning step?
        newlink = re.sub(r'/\&$', '', checked[0])
        # external/internal links
        if external_bool == is_external(newlink, reference):
            validlinks.add(newlink)
    # return
    LOGGER.info('%s links found – %s valid links', len(candidates), len(validlinks))
    return validlinks
