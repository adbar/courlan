## This file is available from https://github.com/adbar/urltools
## under GNU GPL v3 license

import logging
import socket

import requests


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
    headers = requests.utils.default_headers()
    #headers.update({
    #    "Connection" : "close",  # another way to cover tracks
    #    "User-Agent" : str(sample(settings.USER_AGENTS, 1)), # select a random user agent
    #})
    try:
        rhead = requests.head(url, allow_redirects=True, headers=headers)
    except (requests.exceptions.MissingSchema, requests.exceptions.InvalidURL):
        logging.error('malformed URL: %s', url)
    except requests.exceptions.TooManyRedirects:
        logging.error('redirects: %s', url)
    except requests.exceptions.SSLError as err:
        logging.error('SSL: %s %s', url, err)
    except (socket.timeout, requests.exceptions.ConnectionError, requests.exceptions.Timeout, socket.error, socket.gaierror) as err:
        logging.error('connection: %s %s', url, err)
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
