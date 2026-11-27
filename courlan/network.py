"""
Functions devoted to requests over the WWW.
"""

import logging
from urllib.parse import urljoin

import urllib3

from .urlutils import get_ascii_url

LOGGER = logging.getLogger(__name__)
# only silence the warning triggered by cert_reqs="CERT_NONE"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


RETRY_STRATEGY = urllib3.util.Retry(
    total=2,
    redirect=2,
    raise_on_redirect=False,
    status_forcelist=[
        429,
        499,
        500,
        502,
        503,
        504,
        509,
        520,
        521,
        522,
        523,
        524,
        525,
        526,
        527,
        530,
        598,
    ],  # unofficial: https://en.wikipedia.org/wiki/List_of_HTTP_status_codes#Unofficial_codes
    backoff_factor=1,
)
HTTP_POOL = urllib3.PoolManager(
    cert_reqs="CERT_NONE", num_pools=100, retries=RETRY_STRATEGY, timeout=10
)

ACCEPTABLE_CODES = {200, 300, 301, 302, 303, 304, 305, 306, 307, 308}

# HEAD not implemented by the server: answer at once, then retry with GET
HEAD_FALLBACK_CODES = {405, 500, 501}
HEAD_RETRY = RETRY_STRATEGY.new(
    status_forcelist=set(RETRY_STRATEGY.status_forcelist or ()) - HEAD_FALLBACK_CODES
)


# Test redirects
def redirection_test(url: str) -> str:
    """Test final URL to handle redirects
    Args:
        url: url to check

    Returns:
        The final URL seen.

    Raises:
        ValueError: if the URL cannot be reached or returns an unacceptable status.
    """
    ascii_url = get_ascii_url(url)
    try:
        response = HTTP_POOL.request("HEAD", ascii_url, retries=HEAD_RETRY)
        if response.status in HEAD_FALLBACK_CODES:
            # headers only, the connection is closed before the body is read
            response = HTTP_POOL.request("GET", ascii_url, preload_content=False)
            response.close()
    except Exception as err:
        LOGGER.warning("cannot reach URL: %s %s", url, err)
        raise ValueError(f"cannot reach URL: {url}") from err
    if response.status in ACCEPTABLE_CODES:
        # geturl() can be a bare path, resolve the last Location against its hop
        final_url = url
        for hop in response.retries.history if response.retries else ():
            if hop.redirect_location:
                final_url = urljoin(hop.url or url, hop.redirect_location)
        LOGGER.debug("result found: %s %s", final_url, response.status)
        return final_url
    raise ValueError(f"cannot reach URL: {url}")
