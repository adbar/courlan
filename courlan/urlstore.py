"""
Defines a URL store which holds URLs along with relevant information.
"""

import bz2
import logging

from collections import defaultdict, deque
from sys import getsizeof as size

import _pickle as pickle  # import pickle

from .filters import lang_filter, validate_url
from .urlutils import get_host_and_path


LOGGER = logging.getLogger(__name__)


def recursive_size(myobject):
    "Recursively approximatate the memory cost of a custom object."
    # compressed bytestring
    if isinstance(myobject, bytes):
        return size(myobject)
    # urlstore deque object
    if isinstance(myobject, deque):
        # return sum(size(()) + size(k) + size(v) for k, v in myobject) + size(myobject)
        return sum(size(k) for k, _ in myobject) + (size(()) + size(False)) * len(myobject) + size(myobject)
    raise ValueError('invalid object type: %s', type(myobject))


class UrlStore:
    "Defines a class to store domain-classified URLs and perform checks against it."
    __slots__ = ('compressed', 'language', 'strict', 'urldict', 'validation', 'visited')
    #__slots__ = ('__dict__')

    def __init__(self, compressed=False, strict=False, language=None, validation=True, visited=False):
        self.compressed = compressed
        self.language = language
        self.strict = strict
        self.urldict = {}
        self.validation = validation
        self.visited = visited

    def _filter_url(self, url):
        # TODO: validate URL / check_url()?
        if self.validation is True and validate_url(url)[0] is False:
            return False
        if self.language is not None and lang_filter(url, self.language, self.strict) is False:
            return False
        return True

    def _filter_urlpaths(self, domain, urls):
        if self.validation is True or self.language is not None:
            return [u for u in urls if self._filter_url(domain + u) is True]
        return urls

    def _buffer_urls(self, data):
        inputdict = defaultdict(deque)
        for url in list(dict.fromkeys(data)):
            # filter
            if self._filter_url(url) is False:
                continue
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
        if self.compressed is True:
            pickled = pickle.dumps(urls, protocol=4)
            new_value = bz2.compress(pickled)
            # be sure to make gains through compression
            if recursive_size(new_value) < len(pickled):  # recursive_size(urls)
            # and len(new_value) < len(pickled) / 6
                self.urldict[domain] = new_value
            else:
                self.urldict[domain] = urls
        else:
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

    def extend_urls(self, domain, leftseries=[], rightseries=[]):
        # filter
        leftseries = self._filter_urlpaths(domain, leftseries)
        rightseries = self._filter_urlpaths(domain, rightseries)
        if not leftseries and not rightseries:
            return
        # load data
        current_deque = self._load_urls(domain)
        in_store = {u[0] for u in current_deque}
        # process and store
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

