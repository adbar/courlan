"""
Functions devoted to requests over the WWW.
"""

## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import logging
import requests


HEADERS = requests.utils.default_headers()


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
    #    "Connection" : "close",  # another way to cover tracks
    #    "User-Agent" : str(sample(settings.USER_AGENTS, 1)), # select a random user agent
    #})
    try:
        rhead = requests.head(url, allow_redirects=True, headers=HEADERS)
    except Exception as err:
        logging.error('unknown: %s %s', url, err) # sys.exc_info()[0]
    else:
        # response
        if rhead.status_code == 200:
            logging.info('redirection found: %s', rhead.url)
            return rhead.url
    #else:
    logging.info('no redirection found: %s', url)
    return None
