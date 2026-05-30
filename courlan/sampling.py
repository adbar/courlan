"""
Utilities dedicated to URL sampling
"""

import logging

# from functools import cmp_to_key
from random import sample

from .urlstore import UrlStore

LOGGER = logging.getLogger(__name__)


def _make_sample(
    urlstore: UrlStore,
    samplesize: int,
    exclude_min: int | None,
    exclude_max: int | None,
) -> list[str]:
    "Iterate through the hosts in store and draw samples."
    output_urls = []
    for domain in urlstore.urldict:  # key=cmp_to_key(locale.strcoll)
        urlpaths = [
            p.path()
            for p in urlstore._load_urls(domain)
            if p.urlpath not in (b"/", None)
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
    return output_urls


def sample_urls(
    input_urls: list[str],
    samplesize: int,
    exclude_min: int | None = None,
    exclude_max: int | None = None,
    strict: bool = False,
    verbose: bool = False,
) -> list[str]:
    """Sample a list of URLs by domain name, optionally using constraints on their number"""
    # logging
    if verbose:
        LOGGER.setLevel(logging.DEBUG)
    else:
        LOGGER.setLevel(logging.ERROR)
    # store
    urlstore = UrlStore(compressed=True, language=None, strict=strict, verbose=verbose)
    urlstore.add_urls(input_urls)
    # return gathered URLs
    return _make_sample(urlstore, samplesize, exclude_min, exclude_max)
