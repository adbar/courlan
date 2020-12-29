"""
Functions devoted to requests over the WWW.
"""

## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import logging
import urllib3

RETRY_STRATEGY = urllib3.util.Retry(
    total=5,
    redirect=5,
    raise_on_redirect=False,
)
HTTP_POOL = urllib3.PoolManager(retries=RETRY_STRATEGY)


# Test redirects
def redirection_test(url):
    """ Test final URL to handle redirects
    Args:
        url: url to check

    Returns:
        The final URL seen.

    Raises:
        Nothing.
    """
    #headers.update({
    #    "User-Agent" : str(sample(settings.USER_AGENTS, 1)), # select a random user agent
    #})
    try:
        rhead = HTTP_POOL.request('HEAD', url)
    except Exception as err:
        logging.error('unknown: %s %s', url, err) # sys.exc_info()[0]
    else:
        # response
        if rhead.status in (200, 300, 301, 302, 303, 304, 305, 306, 307, 308):
            logging.debug('result found: %s %s', rhead.geturl(), rhead.status)
            return rhead.geturl()
    #else:
    logging.debug('no result found: %s', url)
    return None
