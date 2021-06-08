"""
Functions related to URL manipulation and extraction of URL parts.
"""

import re

from urllib.parse import urlparse


from .compatibility import TLD_EXTRACTION, get_fld, get_tld, tldextract


def extract_domain(url, blacklist=None):
    '''Extract domain name information using top-level domain info'''
    if blacklist is None:
        blacklist = set()
    # legacy tldextract code
    if TLD_EXTRACTION is not None:
        tldinfo = TLD_EXTRACTION(url)
        # domain TLD blacklist
        if tldinfo.domain in blacklist:
            return None
        # return domain
        returnval = '.'.join(part for part in tldinfo if part)
    # new code
    else:
        tldinfo = get_tld(url, as_object=True, fail_silently=True)
        # invalid input OR domain TLD blacklist
        if tldinfo is None or tldinfo.domain in blacklist:
            return None
        # return domain
        returnval = tldinfo.fld
    # this step seems necessary to standardize output
    return re.sub(r'^www[0-9]*\.', '', returnval)


def get_base_url(url):
    'Strip URL of some of its parts to get base URL.'
    parsed_url = urlparse(url)
    return parsed_url._replace(path='', params='', query='', fragment='').geturl()


def get_host_and_path(url):
    """Decompose URL in two parts: protocol + host/domain and path."""
    parsed_url = urlparse(url)
    host = parsed_url._replace(path='', params='', query='', fragment='')
    path = parsed_url._replace(scheme='', netloc='')
    return host.geturl(), path.geturl()


def get_hostinfo(url):
    """Extract domain and host info (protocol + host/domain) from a URL."""
    domainname = extract_domain(url)
    parsed_url = urlparse(url)
    host = parsed_url._replace(path='', params='', query='', fragment='')
    return domainname, host.geturl()


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
    # don't try to correct these URLs
    elif url.startswith('{'):
        urlfix = url
    # catchall
    elif not url.startswith('http'):
        urlfix = baseurl + '/' + url
    else:
        urlfix = url
    return urlfix


def is_external(url, reference, ignore_suffix=True):
    '''Determine if a link leads to another host, takes a reference URL or
       tld/tldextract object as input, returns a boolean'''
    # legacy tldextract code
    if TLD_EXTRACTION is not None:
        # reference
        if not isinstance(reference, tldextract.tldextract.ExtractResult):
            reference = TLD_EXTRACTION(reference)
        tldinfo = TLD_EXTRACTION(url)
        if ignore_suffix is True:
            ref_domain, domain = reference.domain, tldinfo.domain
        else:  # '.'.join(ext[-2:]).strip('.')
            ref_domain, domain = reference.registered_domain, tldinfo.registered_domain
    # new tld code
    else:
        if ignore_suffix is True:
            try:
                ref_domain, domain = get_tld(reference, as_object=True, fail_silently=True).domain, \
                                     get_tld(url, as_object=True, fail_silently=True).domain
            # invalid input
            except AttributeError:
                return True
        else:
            ref_domain, domain = get_fld(reference, fail_silently=True), get_fld(url, fail_silently=True)
    # comparison
    if domain != ref_domain:
        return True
    return False
