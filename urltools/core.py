
import logging
import re

from urllib.parse import urlsplit, urldefrag # urlparse urlunparse,

import tldextract

from furl import furl
from url_normalize import url_normalize


from .clean import clean
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




## chain of validators
def urlcheck(url, redbool):
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
        url = clean(url)

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
        if typefilter(url) is False:
            raise ValueError
        if spamfilter(url) is False:
            raise ValueError

        # normalization
        url = url_normalize(url)

    # handle exceptions
    except (AttributeError, UnicodeError, ValueError): # as err:
        logging.debug('url: %s', url)
        return None

    # domain info
    try:
        tldinfo = no_fetch_extract(url)
    except TypeError:
        logging.debug('tld: %s', tldinfo)
        return None
    # domain TLD blacklist
    if tldinfo.domain in blacklist:
        return None

    domain = re.sub(r'^www[0-9]*\.', '', '.'.join(part for part in tldinfo if part))

    ## URL probably OK
    # get potential redirect
    if redbool is True:
        url2 = redirection_test(url)
        if url2 is not None:
            # domain info
            try:
                tldinfo = no_fetch_extract(url2)
            except TypeError:
                logging.debug('tld: %s', tldinfo)
                return None
            # domain TLD blacklist
            if tldinfo.domain in blacklist:
                return None

            domain2 = re.sub(r'^www[0-9]*\.', '', '.'.join(part for part in tldinfo if part))
            if domain2 != domain:
                return (url2, domain2)

    # hot fix: &amp;
    if '&amp;' in url:
        url = url.replace('&amp;', '&')

    return (url, domain)
