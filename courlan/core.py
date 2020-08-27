## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

#import locale
import logging
import re

#from functools import cmp_to_key
from random import sample
from urllib.parse import urlparse, urlsplit, urldefrag # urlunparse,

import tldextract

from furl import furl
from url_normalize import url_normalize

from .clean import clean_url
from .filters import spamfilter, typefilter
from .network import redirection_test
from .settings import *



no_fetch_extract = tldextract.TLDExtract(suffix_list_urls=None)


def validate(parsed_url):
    if bool(parsed_url.scheme) is False or len(parsed_url.netloc) < 4:
        return False
    if parsed_url.scheme not in ('http', 'https'):
        return False
    # if validators.url(parsed_url.geturl(), public=True) is False:
    #    return False
    # default
    return True


def extract_domain(url):
    try:
        tldinfo = no_fetch_extract(url)
    except TypeError:
        logging.debug('tld: %s', tldinfo)
        return None
    # domain TLD blacklist
    if tldinfo.domain in blacklist:
        return None
    # return domain
    return re.sub(r'^www[0-9]*\.', '', '.'.join(part for part in tldinfo if part))


def urlcheck(url, with_redirects=False):
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
        if len(url) >= 500 or len(url) < 10 or not url.startswith('http'):
            raise ValueError

        # clean
        url = clean_url(url)

        parsed_url = urlsplit(url) # was urlparse(url)
        if validate(parsed_url) is True:
            # strip unwanted query parts
            if len(parsed_url.query) > 0:
                fobject = furl(url)
                for qelem in list(fobject.args):
                    teststr = qelem.lower()
                    if teststr not in allowed_parameters and teststr not in controlled_parameters:
                        del fobject.args[qelem]
                    # control language
                    elif teststr in controlled_parameters:
                        if fobject.args[qelem].lower() not in accepted_lang:
                            logging.debug('bad lang: %s %s', url, fobject.args[qelem].lower)
                            raise ValueError
                url = fobject.url
            # strip fragments
            if len(parsed_url.fragment) > 0:
                url, _ = urldefrag(url)
                # url = urlunsplit((parsed_url[0], parsed_url[1], parsed_url[2], parsed_url[3], ''))
        else:
            raise ValueError

        # content filters
        if typefilter(url) is False or spamfilter(url) is False:
            raise ValueError

        # normalization
        url = url_normalize(url)

    # handle exceptions
    except (AttributeError, UnicodeError, ValueError): # as err:
        logging.debug('url: %s', url)
        return None

    # domain info
    domain = extract_domain(url)
    if domain is None:
        return None

    ## URL probably OK
    # get potential redirect
    if with_redirects is True:
        url2 = redirection_test(url)
        if url2 is not None:
            domain2 = extract_domain(url)
            if domain2 is not None and domain2 != domain:
                return (url2, domain2)

    return (url, domain)


def sample_urls(urllist, samplesize, exclude_min=None, exclude_max=None, verbose=False):
    lastseen, urlbuffer, sampled = None, set(), list()
    for url in sorted(urllist): # key=cmp_to_key(locale.strcoll)
        # first basic filter
        if urlcheck(url) is None:
            continue
        # initialize
        parsed_url = urlparse(url)
        if lastseen is None:
            lastseen = parsed_url.netloc
        # dump URL
        # url = parsed_url.geturl()
        # continue collection
        if parsed_url.netloc == lastseen:
            urlbuffer.add(url)
        # sample, drop, fresh start
        else:
            # threshold for too small websites
            if exclude_min is None or len(urlbuffer) >= exclude_min:
                # write all the buffer
                if len(urlbuffer) <= samplesize:
                    sampled.extend(urlbuffer)
                    if verbose is True:
                        print(lastseen, '\t\turls:', len(urlbuffer))
                # or sample URLs
                else:
                    # threshold for too large websites
                    if exclude_max is None or len(urlbuffer) <= exclude_max:
                        sampled.extend(sample(urlbuffer, samplesize))
                        if verbose is True:
                            print(lastseen, '\t\turls:', len(urlbuffer), '\tprop.:', samplesize/len(urlbuffer))
                    else:
                        if verbose is True:
                            print('discarded (exclude size):', lastseen, '\t\turls:', len(urlbuffer))
            else:
                if verbose is True:
                    print('discarded (exclude size):', lastseen, '\t\turls:', len(urlbuffer))
            urlbuffer = set()
            urlbuffer.add(url)
        lastseen = parsed_url.netloc
    return sampled

