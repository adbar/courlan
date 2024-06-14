"""
Functions devoted to requests over the WWW.
"""

import logging
import ssl

from urllib import request

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
        req = request.Request(url, method="HEAD")
        with request.urlopen(req, context=CERTIFI_CONTEXT) as f:
            pass
        if f.status in ACCEPTABLE_CODES:
            return f.url
    except Exception as err:
        LOGGER.warning("unknown error: %s %s", url, err)

    raise ValueError(f"cannot reach URL: {url}")
