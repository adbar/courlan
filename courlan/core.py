"""
Core functions needed to make the module work.
"""

## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

# import locale
import logging
import re

# from functools import cmp_to_key
from random import sample
from typing import List, Optional, Set, Tuple

from .clean import normalize_url, scrub_url
from .filters import (
    basic_filter,
    extension_filter,
    lang_filter,
    path_filter,
    type_filter,
    validate_url,
)
from .network import redirection_test
from .settings import BLACKLIST
from .urlstore import UrlStore
from .urlutils import extract_domain, fix_relative_urls, is_external, is_known_link


LOGGER = logging.getLogger(__name__)

FIND_LINKS_REGEX = re.compile(r"<a [^<>]+?>", re.I)
HREFLANG_REGEX = re.compile(r'hreflang=["\']?([a-z-]+)', re.I)
LINK_REGEX = re.compile(r'href=["\']?([^ ]+?)(["\']|[ >])', re.I)


def check_url(
    url: str,
    strict: bool = False,
    with_redirects: bool = False,
    language: Optional[str] = None,
    with_nav: bool = False,
) -> Optional[Tuple[str, str]]:
    """Check links for appropriateness and sanity
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
            LOGGER.debug("rejected, basic filter: %s", url)
            raise ValueError

        # clean
        url = scrub_url(url)

        # get potential redirect, can raise ValueError
        if with_redirects:
            url = redirection_test(url)

        # spam & structural elements
        if type_filter(url, strict=strict, with_nav=with_nav) is False:
            LOGGER.debug("rejected, type filter: %s", url)
            raise ValueError

        # internationalization and language heuristics in URL
        if language is not None and lang_filter(url, language, strict) is False:
            LOGGER.debug("rejected, lang filter: %s", url)
            raise ValueError

        # split and validate
        validation_test, parsed_url = validate_url(url)
        if validation_test is False:
            LOGGER.debug("rejected, validation test: %s", url)
            raise ValueError

        # content filter based on extensions
        if extension_filter(parsed_url.path) is False:
            LOGGER.debug("rejected, extension filter: %s", url)
            raise ValueError

        # strict content filtering
        if strict and path_filter(parsed_url.path, parsed_url.query) is False:
            LOGGER.debug("rejected, path filter: %s", url)
            raise ValueError

        # normalize
        url = normalize_url(parsed_url, strict, language)

        # domain info: use blacklist in strict mode only
        if strict:
            domain = extract_domain(url, blacklist=BLACKLIST, fast=True)
        else:
            domain = extract_domain(url, fast=True)
        if domain is None:
            LOGGER.debug("rejected, domain name: %s", url)
            return None

    # handle exceptions
    except (AttributeError, ValueError):
        LOGGER.debug("discarded URL: %s", url)
        return None

    return url, domain


def sample_urls(
    input_urls: List[str],
    samplesize: int,
    exclude_min: Optional[int] = None,
    exclude_max: Optional[int] = None,
    strict: bool = False,
    verbose: bool = False,
) -> List[str]:
    """Sample a list of URLs by domain name, optionally using constraints on their number"""
    # logging
    if verbose:
        LOGGER.setLevel(logging.DEBUG)
    else:
        LOGGER.setLevel(logging.ERROR)
    # store
    output_urls = []
    use_compression = len(input_urls) > 10**6
    urlstore = UrlStore(
        compressed=use_compression, language=None, strict=strict, verbose=verbose
    )
    urlstore.add_urls(sorted(input_urls))
    # iterate
    for domain in urlstore.urldict:  # key=cmp_to_key(locale.strcoll)
        urlpaths = [
            p.urlpath
            for p in urlstore._load_urls(domain)
            if p.urlpath not in ("/", None)
        ]
        # too few or too many URLs
        if (
            not urlpaths
            or exclude_min is not None
            and len(urlpaths) < exclude_min
            or exclude_max is not None
            and len(urlpaths) > exclude_max
        ):
            LOGGER.warning("discarded (size): %s\t\turls: %s", domain, len(urlpaths))
            continue
        # sample
        if len(urlpaths) > samplesize:
            mysample = sorted(sample(urlpaths, k=samplesize))
        else:
            mysample = urlpaths
        output_urls.extend([domain + p for p in mysample])
        LOGGER.debug(
            "%s\t\turls: %s\tprop.: %s",
            domain,
            len(mysample),
            len(mysample) / len(urlpaths),
        )
    # return gathered URLs
    return output_urls


def extract_links(
    pagecontent: str,
    base_url: str,
    external_bool: bool,
    no_filter: bool = False,
    language: Optional[str] = None,
    strict: bool = True,
    with_nav: bool = False,
    redirects: bool = False,
    reference: Optional[str] = None,
) -> Set[str]:
    """Filter links in a HTML document using a series of heuristics
    Args:
        pagecontent: whole page in binary format
        base_url: beginning of the URL, without path, fragment and query
        external_bool: set to True for external links only, False for
                  internal links only
        no_filter: override settings and bypass checks to return all possible URLs
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
    candidates, validlinks = set(), set()  # type: Set[str], Set[str]
    if not pagecontent:
        return validlinks
    # define host reference
    reference = reference or base_url
    # extract links
    for link in (m[0] for m in FIND_LINKS_REGEX.finditer(pagecontent)):
        if "rel" in link and "nofollow" in link:
            continue
        # https://en.wikipedia.org/wiki/Hreflang
        if no_filter is False and language is not None and "hreflang" in link:
            langmatch = HREFLANG_REGEX.search(link)
            if langmatch and (
                langmatch[1].startswith(language) or langmatch[1] == "x-default"
            ):
                linkmatch = LINK_REGEX.search(link)
                if linkmatch:
                    candidates.add(linkmatch[1])
        # default
        else:
            linkmatch = LINK_REGEX.search(link)
            if linkmatch:
                candidates.add(linkmatch[1])
    # filter candidates
    for link in candidates:
        # repair using base
        if not link.startswith("http"):
            link = fix_relative_urls(base_url, link)
        # check
        if no_filter is False:
            checked = check_url(
                link,
                strict=strict,
                with_nav=with_nav,
                with_redirects=redirects,
                language=language,
            )
            if checked is None:
                continue
            link = checked[0]
            # external/internal links
            if external_bool != is_external(
                url=link, reference=reference, ignore_suffix=True
            ):
                continue
        if is_known_link(link, validlinks):
            continue
        validlinks.add(link)
    # return
    LOGGER.info("%s links found – %s valid links", len(candidates), len(validlinks))
    return validlinks
