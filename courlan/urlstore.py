"""
Defines a URL store which holds URLs along with relevant information.
"""

import bz2
import logging
import pickle
import signal
import sys

from collections import defaultdict, deque
from datetime import datetime, timedelta

from .filters import lang_filter, validate_url
from .urlutils import get_host_and_path, is_known_link


LOGGER = logging.getLogger(__name__)


class DomainEntry:
    "Class to record host-related information and URL paths."
    __slots__ = ('all_visited', 'count', 'rules', 'timestamp', 'tuples')

    def __init__(self):
        self.all_visited = False
        self.count = 0
        self.rules = None
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
    __slots__ = ('compressed', 'done', 'language', 'strict', 'urldict', 'validation')

    def __init__(self, compressed=False, language=None, strict=False, validation=True):
        self.compressed = compressed
        self.done = False
        self.language = language
        self.strict = strict
        self.urldict = defaultdict(DomainEntry)
        self.validation = validation

        def dump_unvisited_urls(num, frame):
            LOGGER.warning('Processing interrupted, dumping unvisited URLs from %s hosts', len(self.urldict))
            for domain in self.urldict:
                print('\n'.join([domain + u.urlpath for u in self._load_urls(domain) if u.visited is False]), file=sys.stderr)
            sys.exit()

        # don't use the following on Windows
        if not sys.platform.startswith('win'):
            signal.signal(signal.SIGINT, dump_unvisited_urls)
            signal.signal(signal.SIGTERM, dump_unvisited_urls)

    def _filter_url(self, url):
        # TODO: validate URL / check_url()?
        if self.validation is True and validate_url(url)[0] is False:
            return False
        if self.language is not None and lang_filter(url, self.language, self.strict) is False:
            return False
        return True

    #def _filter_urlpaths(self, domain, urls):
    #    if self.validation is True or self.language is not None:
    #        return [u for u in urls if self._filter_url(domain + u) is True]
    #    return urls

    def _buffer_urls(self, data, visited=False):
        inputdict = defaultdict(deque)
        #known = set()
        for url in list(dict.fromkeys(data)):
            # filter
            if self._filter_url(url) is False:
                continue
            # test for duplicates
            #if is_known_url(url, known):
            #    continue
            # segment URL and add to domain dictionary
            try:
                hostinfo, urlpath = get_host_and_path(url)
                inputdict[hostinfo].append(UrlPathTuple(urlpath, visited))
                #known.add(url)
            except ValueError:
                LOGGER.warning('Could not parse URL, discarding: %s', url)
        return inputdict

    def _load_urls(self, domain):
        value = self.urldict[domain].tuples
        if isinstance(value, bytes):
            return pickle.loads(bz2.decompress(value))
        return value

    def _store_urls(self, domain, to_right=None, timestamp=None, to_left=None):
        if domain in self.urldict:
            urls = self._load_urls(domain)
            known = {u.urlpath for u in urls}
        else:
            urls = deque()
            known = set()
        # check if the link or its variants are known
        if to_right is not None:
            urls.extend(t for t in to_right if not is_known_link(t.urlpath, known))
        if to_left is not None:
            urls.extendleft(t for t in to_left if not is_known_link(t.urlpath, known))
        # compression
        if self.compressed is True:
            self.urldict[domain].tuples =  bz2.compress(pickle.dumps(urls, protocol=4))
        else:
            self.urldict[domain].tuples = urls
        # adjust all_visited status
        self.urldict[domain].all_visited = all(u.visited is True for u in urls)
        # timestamp/backoff value
        if timestamp is not None:
            self.urldict[domain].timestamp = timestamp

    def _search_urls(self, urls, switch=None):
        # init
        last_domain, known_paths = None, set()
        remaining_urls = {u: None for u in urls}
        # iterate
        for url in sorted(remaining_urls):
            hostinfo, urlpath = get_host_and_path(url)
            # examine domain
            if hostinfo != last_domain:
                last_domain = hostinfo
                if switch == 1:
                    known_paths = {u.urlpath for u in self._load_urls(hostinfo)}
                elif switch == 2:
                    known_paths = {u.urlpath: u.visited for u in self._load_urls(hostinfo)}
            # run checks
            if urlpath in known_paths:
                # case 1: the path matches, case 2: visited URL
                if switch == 1 or (switch == 2 and known_paths[urlpath] is True):
                    del remaining_urls[url]
        # preserve input order
        return list(remaining_urls)

    def add_urls(self, urls=None, appendleft=None, visited=False):
        """Add a list of URLs to the (possibly) existing one.
        Optional: append certain URLs to the left,
        specify if the URLs have already been visited."""
        if urls:
            for host, urltuples in self._buffer_urls(urls, visited).items():
                self._store_urls(host, to_right=urltuples)
        if appendleft:
            for host, urltuples in self._buffer_urls(appendleft, visited).items():
                self._store_urls(host, to_left=urltuples)

    def get_url(self, domain):
        "Retrieve a single URL and consider it to be visited (with corresponding timestamp)."
        # not fully used
        if self.urldict[domain].all_visited is False:
            url_tuples = self._load_urls(domain)
            # get first non-seen url
            for url in url_tuples:
                if url.visited is False:
                    url.visited = True
                    self.urldict[domain].count += 1
                    self._store_urls(domain, url_tuples, timestamp=datetime.now())
                    return domain + url.urlpath
        # nothing to draw from
        self.urldict[domain].all_visited = True
        return None

    def is_known(self, url):
        "Check if the given URL has already been stored."
        hostinfo, urlpath = get_host_and_path(url)
        values = self._load_urls(hostinfo)
        # returns False if domain or URL is new
        return urlpath in {u.urlpath for u in values}

    def find_known_urls(self, domain):
        """Get all already known URLs for the given domain (ex. "https://example.org")."""
        values = self._load_urls(domain)
        return [domain + u.urlpath for u in values]

    def filter_unknown_urls(self, urls):
        "Take a list of URLs and return the currently unknown ones."
        return self._search_urls(urls, switch=1)

    def has_been_visited(self, url):
        "Check if the given URL has already been visited.."
        hostinfo, urlpath = get_host_and_path(url)
        values = self._load_urls(hostinfo)
        known_urlpaths = {u.urlpath: u.visited for u in values}
        # defaults to None, thus False
        return known_urlpaths.get(urlpath) or False

    def find_unvisited_urls(self, domain):
        "Get all unvisited URLs for the given domain."
        values = self._load_urls(domain)
        return [domain + u.urlpath for u in values if u.visited is False]

    def filter_unvisited_urls(self, urls):
        "Take a list of URLs and return the currently unvisited ones."
        return self._search_urls(urls, switch=2)

    def get_download_urls(self, timelimit=10):
        """Get a list of immediately downloadable URLs according to the given
           time limit per domain."""
        potential = [d for d in self.urldict if self.urldict[d].all_visited is False]
        if not potential:
            self.done = True
            return None
        targets = []
        for domain in potential:
            timestamp = self.urldict[domain].timestamp
            if timestamp is None or (datetime.now() - timestamp).total_seconds() > timelimit:
                targets.append(domain)
        # get corresponding URLs and filter out None values
        return list(filter(None, [self.get_url(domain) for domain in targets]))

    def establish_download_schedule(self, max_urls=100, time_limit=10):
        """Get up to the specified number of URLs along with a suitable
           backoff schedule (in seconds)."""
        # see which domains are free
        potential = [d for d in self.urldict if self.urldict[d].all_visited is False]
        if not potential:
            self.done = True
            return []
        # variables init
        per_domain = max_urls // len(potential) or 1
        targets = []
        # iterate potential domains
        for domain in potential:
            url_tuples = self._load_urls(domain)
            # load urls
            urlpaths = []
            # get first non-seen urls
            for url in url_tuples:
                if len(urlpaths) >= per_domain or (len(targets) + len(urlpaths)) >= max_urls:
                    break
                if url.visited is False:
                    urlpaths.append(url.urlpath)
                    url.visited = True
                    self.urldict[domain].count += 1
            # determine timestamps
            now = datetime.now()
            original_timestamp = self.urldict[domain].timestamp
            if original_timestamp is None or (now - original_timestamp).total_seconds() > time_limit:
                schedule_secs = 0
            else:
                schedule_secs = time_limit - float('{:.2f}'.format((now - original_timestamp).total_seconds()))
            for urlpath in urlpaths:
                targets.append((schedule_secs, domain + urlpath))
                schedule_secs += time_limit
            # calculate difference and offset last addition
            total_diff = now + timedelta(0, schedule_secs - time_limit)
            # store new info
            self._store_urls(domain, url_tuples, timestamp=total_diff)
        # sort by first tuple element (time in secs)
        return sorted(targets, key=lambda x: x[0])

    def dump_urls(self):
        "Print all URLs in store (URL + TAB + visited or not)."
        for domain in self.urldict:
            print('\n'.join([domain + u.urlpath + '\t' + str(u.visited) for u in self._load_urls(domain)]))
