"""
Defines a URL store which holds URLs along with relevant information.
"""

import bz2
import logging

from collections import defaultdict, deque
from datetime import datetime
from sys import getsizeof as size

import _pickle as pickle  # import pickle

from .filters import lang_filter, validate_url
from .urlutils import get_host_and_path


LOGGER = logging.getLogger(__name__)


class DomainEntry:
    "Class to record host-related information and URL paths."
    __slots__ = ('all_visited', 'timestamp', 'tuples')

    def __init__(self):
        self.all_visited = False
        self.tuples = deque()
        self.timestamp = None


class UrlPathTuple:
    "Class storing information for URL paths relative to a domain/host."
    __slots__ = ('urlpath', 'visited')

    def __init__(self, urlpath, visited):
        self.urlpath = urlpath
        self.visited = visited


class UrlStore:
    "Defines a class to store domain-classified URLs and perform checks against it."
    __slots__ = ('compressed', 'language', 'strict', 'urldict', 'validation')

    def __init__(self, compressed=False, language=None, strict=False, validation=True):
        self.compressed = compressed
        self.language = language
        self.strict = strict
        self.urldict = {}
        self.validation = validation

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

    def _buffer_urls(self, data, visited=False):
        inputdict = defaultdict(deque)
        for url in list(dict.fromkeys(data)):
            # filter
            if self._filter_url(url) is False:
                continue
            # segment URL and add to domain dictionary
            try:
                hostinfo, urlpath = get_host_and_path(url)
                inputdict[hostinfo].append(UrlPathTuple(urlpath, visited))
            except ValueError:
                LOGGER.warning('Could not parse URL, discarding: %s', url)
        return inputdict

    def _load_urls(self, domain):
        if domain in self.urldict:
            value = self.urldict[domain].tuples
            if isinstance(value, bytes):
                return pickle.loads(bz2.decompress(value))
            return value
        return deque()

    def _store_urls(self, domain, urls, set_timestamp=False):
        # init
        if domain not in self.urldict:
            self.urldict[domain] = DomainEntry()
        # compression
        if self.compressed is True:
            pickled = pickle.dumps(urls, protocol=4)
            new_value = bz2.compress(pickled)
            # be sure to make gains through compression
            if size(new_value) < size(pickled):
                self.urldict[domain].tuples = new_value
            else:
                self.urldict[domain].tuples = urls
        else:
            self.urldict[domain].tuples = urls
        # adjust all_visited status
        if any(u.visited is False for u in urls):
            self.urldict[domain].all_visited = False
        else:
            self.urldict[domain].all_visited = True
        # timestamp/backoff value
        if set_timestamp is True:
            self.urldict[domain].timestamp = datetime.now()

    def _search_urls(self, urls, switch=None):
        # init
        last_domain, known_paths = None, set()
        remaining_urls = {u: None for u in urls}
        # iterate
        for url in sorted(remaining_urls):
            hostinfo, urlpath = get_host_and_path(url)
            # already seen
            if hostinfo in self.urldict and self.urldict[hostinfo].all_visited is True:
                del remaining_urls[url]
                continue
            # examine domain
            if hostinfo != last_domain:
                last_domain = hostinfo
                if switch == 1:
                    known_paths = {u.urlpath for u in self._load_urls(hostinfo)}
                elif switch == 2:
                    known_paths = {u.urlpath: u.visited for u in self._load_urls(hostinfo)}
            # process result
            if not known_paths:
                continue
            if switch == 1 and urlpath in known_paths:
                del remaining_urls[url]
            elif switch == 2 and urlpath in known_paths and known_paths[urlpath] is True:
                del remaining_urls[url]
        # preserve input order
        return list(remaining_urls)

    def add_data(self, data, visited=False):
        for key, value in self._buffer_urls(data, visited).items():
            self._store_urls(key, value)

    def extend_urls(self, domain, leftseries=[], rightseries=[], visited=False):
        # filter
        leftseries = self._filter_urlpaths(domain, leftseries)
        rightseries = self._filter_urlpaths(domain, rightseries)
        if not leftseries and not rightseries:
            return
        # load data
        current_deque = self._load_urls(domain)
        in_store = {u.urlpath for u in current_deque}
        # process and store
        current_deque.extendleft([UrlPathTuple(u, visited) for u in leftseries if not u in in_store])
        current_deque.extend([UrlPathTuple(u, visited) for u in rightseries if not u in in_store])
        self._store_urls(domain, current_deque)

    def get_url(self, domain):
        # domain is full
        if self.urldict[domain].all_visited is True:
            return None
        url_tuples = self._load_urls(domain)
        i = 0
        # get first non-seen url
        for url in url_tuples:
            if url.visited is False:
                # set visited to True
                url.visited = True
                break
            i += 1
        # store info
        self._store_urls(domain, url_tuples, set_timestamp=True)
        return domain + url.urlpath

    def is_known(self, url):
        hostinfo, urlpath = get_host_and_path(url)
        values = self._load_urls(hostinfo)
        if not values:
            return False
        return urlpath in {u.urlpath for u in values}

    def find_unknown_urls(self, urls):
        return self._search_urls(urls, switch=1)

    def has_been_visited(self, url):
        hostinfo, urlpath = get_host_and_path(url)
        values = self._load_urls(hostinfo)
        if not values:
            return False
        known_urlpaths = {u.urlpath: u.visited for u in values}
        return known_urlpaths.get(urlpath) or False

    def find_unvisited_urls(self, urls):
        return self._search_urls(urls, switch=2)

    def get_download_urls(self, limit=10):
        now = datetime.now()
        targets = []
        potential = [d for d in self.urldict if self.urldict[d].all_visited is False]
        if not potential:
            return None
        for domain in potential:
            timestamp = self.urldict[domain].timestamp
            if timestamp is None or (now - timestamp).total_seconds() > limit:
                targets.append(domain)
        # get corresponding URLs and filter out None values
        return list(filter(None, [self.get_url(domain) for domain in targets]))

    def dump_urls(self):
        for domain in self.urldict:
            print('\n'.join([domain + u.urlpath for u in self._load_urls(domain)]))

