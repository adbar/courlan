"""
Functions devoted to requests over the WWW.
"""

import logging
import ssl
import urllib.request

from typing import Optional
from urllib.error import HTTPError

import certifi


CERTIFI_CONTEXT = ssl.create_default_context(cafile=certifi.where())

LOGGER = logging.getLogger(__name__)

ACCEPTABLE_CODES = {200, 300, 301, 302, 303, 304, 305, 306, 307, 308}


def redirection_test(url: str) -> str:
    """Test final URL to handle redirects
    Args:
        url: url to check

    Returns:
        The final URL seen.

    Raises:
        Nothing.
    """
    try:
        req = urllib.request.Request(url, method="HEAD")
        rhead = urllib.request.urlopen(req, context=CERTIFI_CONTEXT)
    except HTTPError as error:
        if error.status in ACCEPTABLE_CODES:
            return error.url
    except Exception as err:
        LOGGER.warning("unknown error: %s %s", url, err)
    else:
        return rhead.url

    raise ValueError(f"cannot reach URL: {url}")
