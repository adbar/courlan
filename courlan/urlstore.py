"""
Defines a URL store which holds URLs along with relevant information.
"""

import bz2
import logging
import pickle  #import _pickle as pickle

from collections import defaultdict, deque

# from pympler import asizeof

from .filters import validate_url
from .urlutils import get_host_and_path


LOGGER = logging.getLogger(__name__)


class UrlStore:
    "Defines a class to store domain-classified URLs and perform checks against it."
    __slots__ = ('compressed', 'target_language', 'urldict', 'visited')  #__slots__ = ('__dict__')

    def __init__(self, visited=False, compressed=False, target_language=None):
        self.visited = visited
        self.compressed = compressed
        self.target_language = target_language
        self.urldict = {}

    def _buffer_urls(self, data):
        inputdict = defaultdict(deque)
        for url in list(dict.fromkeys(data)):
            # validate URL, target_language
            #if validate_url(url)[0] is False:
            #    continue
            # segment URL and add to domain dictionary
            try:
                hostinfo, urlpath = get_host_and_path(url)
                inputdict[hostinfo].append((urlpath, self.visited))
            except ValueError:
                LOGGER.warning('Could not parse URL, discarding: %s', url)
        return inputdict

    def _load_urls(self, domain):
        value = self.urldict.get(domain)
        if value is not None:
            if isinstance(value, bytes):
                return pickle.loads(bz2.decompress(value))
            return value
        return deque()

    def _store_urls(self, domain, urls):
        #if self.compressed is True:
        #    #pickled = pickle.dumps(urls, protocol=4)
        #    #new_value = bz2.compress(pickled)
        #    new_value = bz2.compress(pickle.dumps(urls, protocol=4))
        #    # be sure to make gains through compression
        #    if asizeof.asizeof(new_value) < asizeof.asizeof(urls):
        #    #if len(new_value) < len(pickled) / 6:
        #        self.urldict[domain] = new_value
        #    else:
        #        self.urldict[domain] = urls
        #else:
        self.urldict[domain] = urls

    def _search_urls(self, urls, switch=None):
        # init
        last_domain, known_paths = None, set()
        remaining_urls = {u: None for u in urls}
        # iterate
        for url in sorted(remaining_urls):
            hostinfo, urlpath = get_host_and_path(url)
            if hostinfo != last_domain:
                last_domain = hostinfo
                if switch == 1:
                    known_paths = {u[0] for u in self._load_urls(hostinfo)}
                elif switch == 2:
                    known_paths = {u[0]: u[1] for u in self._load_urls(hostinfo)}
            if not known_paths:
                continue
            if switch == 1 and urlpath in known_paths:
                del remaining_urls[url]
            elif switch == 2 and urlpath in known_paths and known_paths[urlpath] is True:
                del remaining_urls[url]
        # preserve input order
        return list(remaining_urls)

    def add_data(self, data):
        for key, value in self._buffer_urls(data).items():
            self._store_urls(key, value)

    def extend_urls(self, domain, leftseries=None, rightseries=None):
        leftseries, rightseries = leftseries or [], rightseries or []
        current_deque = self._load_urls(domain)
        in_store = {u[0] for u in current_deque}
        #to_add = self._buffer_urls(self, urls)
        current_deque.extendleft([(u, self.visited) for u in leftseries if not u in in_store])
        current_deque.extend([(u, self.visited) for u in rightseries if not u in in_store])
        self._store_urls(domain, current_deque)

    def get_url(self, domain):
        candidate = None
        url_tuples = self._load_urls(domain)
        i = 0
        # get first non-seen url
        for urlpath, visited in url_tuples:
            if visited is False:
                candidate = urlpath
                # set visited to True
                url_tuples[i] = (urlpath, True)
                break
            i += 1
        # store info
        self._store_urls(domain, url_tuples)
        return candidate

    def is_known(self, url):
        hostinfo, urlpath = get_host_and_path(url)
        values = self._load_urls(hostinfo)
        if not values:
            return False
        return urlpath in {u[0] for u in values}

    def find_unknown_urls(self, urls):
        return self._search_urls(urls, switch=1)

    def has_been_visited(self, url):
        hostinfo, urlpath = get_host_and_path(url)
        values = self._load_urls(hostinfo)
        if not values:
            return False
        known_urlpaths = {u[0]: u[1] for u in values}
        if urlpath not in known_urlpaths:
            return False
        return known_urlpaths[urlpath]

    def find_unvisited_urls(self, urls):
        return self._search_urls(urls, switch=2)

