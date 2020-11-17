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
from .filters import basic_filter, extension_filter, lang_filter, \
                     PATH_FILTER, spam_filter, type_filter, validate_url
from .network import redirection_test
from .settings import BLACKLIST


LOGGER = logging.getLogger(__name__)

# extract callable that falls back to the included TLD snapshot, no live HTTP fetching
TLD_EXTRACTION = tldextract.TLDExtract(suffix_list_urls=None)


def extract_domain(url, blacklist={}):
    '''Extract domain name information using top-level domain info'''
    tldinfo = TLD_EXTRACTION(url)
    # domain TLD blacklist
    if tldinfo.domain in blacklist:
        return None
    # return domain
    return re.sub(r'^www[0-9]*\.', '', '.'.join(part for part in tldinfo if part))


def check_url(url, strict=False, with_redirects=False, language=None):
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


def is_external(url, reference, ignore_suffix=True):
    '''Determine if a link leads to another host, takes a reference URL or 
       tldextract object as input, returns a boolean'''
    # reference
    if not isinstance(reference, tldextract.tldextract.ExtractResult):
        reference = TLD_EXTRACTION(reference)
    if ignore_suffix is True:
        ref_domain = reference.domain
    else:  # '.'.join(ext[-2:]).strip('.')
        ref_domain = reference.registered_domain
    # url
    tldinfo = TLD_EXTRACTION(url)
    if ignore_suffix is True:
        domain = tldinfo.domain
    else:
        domain = tldinfo.registered_domain
    # comparison
    if domain != ref_domain:
        return True
    return False


def extract_links(pagecontent, base_url, external_bool, language=None):
    """ Filter links in a HTML document using regular expressions
    Args:
        pagecontent: whole page in binary format
        base_url: needed to reconstruct absolute links
        external_bool: shift from internal to external

    Returns:
        A set containing sanity-checked HTTP links.

    Raises:
        Nothing.
    """
    # extract links
    candidates = set()
    for link in re.findall(r'<a .+?>', pagecontent):
        # https://en.wikipedia.org/wiki/Hreflang
        if language in ('de', 'en') and 'hreflang' in link:
            if language == 'de' and re.search(r'hreflang="(de|DE|x-default)', link):
                mymatch = re.search(r'href="(.+?)"', link)
                if mymatch:
                    candidates.add(mymatch.group(1))
            elif language == 'en' and re.search(r'hreflang="(en|EN|x-default)', link):
                mymatch = re.search(r'href="(.+?)"', link)
                if mymatch:
                    candidates.add(mymatch.group(1))
        # default
        else:
            mymatch = re.search(r'href="(.+?)"', link)
            if mymatch:
                candidates.add(mymatch.group(1))
    # filter candidates
    reference = TLD_EXTRACTION(base_url)
    validlinks = set()
    for link in candidates:
        # repair using base
        if not link.startswith('http'):
            link = base_url + link
        # check
        checked = check_url(link, strict=True, with_redirects=False, language=language)
        if checked is None:
            continue
        # external links
        if external_bool is True and is_external(link, reference) is True:
            validlinks.add(checked[0])
        # internal links
        elif external_bool is False and is_external(link, reference) is False:
            validlinks.add(checked[0])
    # return
    LOGGER.info('%s links found – %s valid links', len(candidates), len(validlinks))
    return validlinks
