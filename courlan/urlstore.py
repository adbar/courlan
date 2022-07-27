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
from threading import Lock
from typing import Any, DefaultDict, Deque, Dict, List, Optional, Tuple, Union

from urllib.robotparser import RobotFileParser

from .filters import lang_filter, validate_url
from .urlutils import get_host_and_path, is_known_link


LOGGER = logging.getLogger(__name__)


class DomainEntry:
    "Class to record host-related information and URL paths."
    __slots__ = ("all_visited", "count", "rules", "timestamp", "tuples")

    def __init__(self) -> None:
        self.all_visited: bool = False
        self.count: int = 0
        self.rules: Optional[RobotFileParser] = None
        self.tuples: Deque[UrlPathTuple] = deque()
        self.timestamp: Optional[Any] = None


class UrlPathTuple:
    "Class storing information for URL paths relative to a domain/host."
    __slots__ = ("urlpath", "visited")

    def __init__(self, urlpath: str, visited: bool) -> None:
        self.urlpath: str = urlpath
        self.visited: bool = visited


class UrlStore:
    "Defines a class to store domain-classified URLs and perform checks against it."
    __slots__ = ("compressed", "done", "language", "strict", "urldict", "_lock")

    def __init__(
        self,
        compressed: bool = False,
        language: Optional[str] = None,
        strict: bool = False,
    ) -> None:
        self.compressed: bool = compressed
        self.done: bool = False
        self.language: Optional[str] = language
        self.strict: bool = strict
        self.urldict: DefaultDict[str, DomainEntry] = defaultdict(DomainEntry)
        self._lock: Lock = Lock()

        def dump_unvisited_urls(num: Any, frame: Any) -> None:
            LOGGER.warning(
                "Processing interrupted, dumping unvisited URLs from %s hosts",
                len(self.urldict),
            )
            for domain in self.urldict:
                print(
                    "\n".join(
                        [
                            domain + u.urlpath
                            for u in self._load_urls(domain)
                            if not u.visited
                        ]
                    ),
                    file=sys.stderr,
                )
            sys.exit()

        # don't use the following on Windows
        if not sys.platform.startswith("win"):
            signal.signal(signal.SIGINT, dump_unvisited_urls)
            signal.signal(signal.SIGTERM, dump_unvisited_urls)

    # def _filter_urlpaths(self, domain, urls):
    #    if self.validation or self.language is not None:
    #        return [u for u in urls if self._filter_url(domain + u)]
    #    return urls

    def _buffer_urls(
        self, data: List[str], visited: bool = False
    ) -> DefaultDict[str, Deque[UrlPathTuple]]:
        inputdict: DefaultDict[str, Deque[UrlPathTuple]] = defaultdict(deque)
        for url in list(dict.fromkeys(data)):
            # segment URL and add to domain dictionary
            try:
                # validate
                validation_result, parsed_url = validate_url(url)
                if validation_result is False:
                    LOGGER.debug("Invalid URL: %s", url)
                    raise ValueError
                # filter
                if (
                    self.language is not None
                    and lang_filter(url, self.language, self.strict) is False
                ):
                    LOGGER.debug("Wrong language: %s", url)
                    raise ValueError
                hostinfo, urlpath = get_host_and_path(parsed_url)
                inputdict[hostinfo].append(UrlPathTuple(urlpath, visited))
            except (TypeError, ValueError):
                LOGGER.warning("Discarding URL: %s", url)
        return inputdict

    def _load_urls(self, domain: str) -> Deque[UrlPathTuple]:
        value = self.urldict[domain].tuples
        if isinstance(value, bytes):
            return pickle.loads(bz2.decompress(value))
        return value

    def _store_urls(
        self,
        domain: str,
        to_right: Optional[Deque[UrlPathTuple]] = None,
        timestamp: Optional[datetime] = None,
        to_left: Optional[Deque[UrlPathTuple]] = None,
    ) -> None:
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
        # use lock
        with self._lock:
            # compression
            if self.compressed:
                self.urldict[domain].tuples = bz2.compress(  # type: ignore
                    pickle.dumps(urls, protocol=4)
                )
            else:
                self.urldict[domain].tuples = urls
            # adjust all_visited status
            self.urldict[domain].all_visited = all(u.visited for u in urls)
            # timestamp/backoff value
            if timestamp is not None:
                self.urldict[domain].timestamp = timestamp

    def _search_urls(
        self, urls: List[str], switch: Optional[int] = None
    ) -> List[Union[Any, str]]:
        # init
        last_domain: Optional[str] = None
        known_paths: Dict[str, Optional[bool]] = {}
        remaining_urls = {u: None for u in urls}
        # iterate
        for url in sorted(remaining_urls):
            hostinfo, urlpath = get_host_and_path(url)
            # examine domain
            if hostinfo != last_domain:
                last_domain = hostinfo
                if switch == 1:
                    known_paths = {u.urlpath: None for u in self._load_urls(hostinfo)}
                elif switch == 2:
                    known_paths = {
                        u.urlpath: u.visited for u in self._load_urls(hostinfo)
                    }
            # run checks: case 1: the path matches, case 2: visited URL
            if urlpath in known_paths and (
                switch == 1 or (switch == 2 and known_paths[urlpath])
            ):
                del remaining_urls[url]
        # preserve input order
        return list(remaining_urls)

    def _timestamp(self, domain: str) -> Optional[datetime]:
        return self.urldict[domain].timestamp

    # URL MANIPULATION AND INFO

    def add_urls(
        self,
        urls: Optional[List[str]] = None,
        appendleft: Optional[List[str]] = None,
        visited: bool = False,
    ) -> None:
        """Add a list of URLs to the (possibly) existing one.
        Optional: append certain URLs to the left,
        specify if the URLs have already been visited."""
        if urls:
            for host, urltuples in self._buffer_urls(urls, visited).items():
                self._store_urls(host, to_right=urltuples)
        if appendleft:
            for host, urltuples in self._buffer_urls(appendleft, visited).items():
                self._store_urls(host, to_left=urltuples)

    def is_known(self, url: str) -> bool:
        "Check if the given URL has already been stored."
        hostinfo, urlpath = get_host_and_path(url)
        values = self._load_urls(hostinfo)
        # returns False if domain or URL is new
        return urlpath in {u.urlpath for u in values}

    def find_known_urls(self, domain: str) -> List[str]:
        """Get all already known URLs for the given domain (ex. "https://example.org")."""
        values = self._load_urls(domain)
        return [domain + u.urlpath for u in values]

    def filter_unknown_urls(self, urls: List[str]) -> List[str]:
        "Take a list of URLs and return the currently unknown ones."
        return self._search_urls(urls, switch=1)

    def get_known_domains(self) -> List[str]:
        "Return all known domains as a list."
        return list(self.urldict)

    def is_exhausted_domain(self, domain: str) -> bool:
        "Tell if all known URLs for the website have been visited."
        if domain in self.urldict:
            return self.urldict[domain].all_visited
        raise KeyError("website not in store")

    # URL-BASED QUERIES

    def has_been_visited(self, url: str) -> bool:
        "Check if the given URL has already been visited.."
        hostinfo, urlpath = get_host_and_path(url)
        values = self._load_urls(hostinfo)
        known_urlpaths = {u.urlpath: u.visited for u in values}
        # defaults to None, thus False
        return known_urlpaths.get(urlpath) or False

    def find_unvisited_urls(self, domain: str) -> List[str]:
        "Get all unvisited URLs for the given domain."
        values = self._load_urls(domain)
        return [domain + u.urlpath for u in values if not u.visited]

    def filter_unvisited_urls(self, urls: List[str]) -> List[Union[Any, str]]:
        "Take a list of URLs and return the currently unvisited ones."
        return self._search_urls(urls, switch=2)

    def unvisited_websites_number(self) -> int:
        "Return the number of websites for which there are still URLs to visit."
        return len([d for d in self.urldict if not self.urldict[d].all_visited])

    # DOWNLOADS

    def get_url(self, domain: str) -> Optional[str]:
        "Retrieve a single URL and consider it to be visited (with corresponding timestamp)."
        # not fully used
        if not self.urldict[domain].all_visited:
            url_tuples = self._load_urls(domain)
            # get first non-seen url
            for url in url_tuples:
                if not url.visited:
                    url.visited = True
                    with self._lock:
                        self.urldict[domain].count += 1
                    self._store_urls(domain, url_tuples, timestamp=datetime.now())
                    return domain + url.urlpath
        # nothing to draw from
        with self._lock:
            self.urldict[domain].all_visited = True
        return None

    def get_download_urls(self, timelimit: int = 10) -> Optional[List[str]]:
        """Get a list of immediately downloadable URLs according to the given
        time limit per domain."""
        with self._lock:
            potential = [d for d in self.urldict if not self.urldict[d].all_visited]
        if not potential:
            self.done = True
            return None
        targets = []
        for domain in potential:
            timestamp = self._timestamp(domain)
            if (
                timestamp is None
                or (datetime.now() - timestamp).total_seconds() > timelimit
            ):
                targets.append(domain)
        # get corresponding URLs and filter out None values
        return list(filter(None, [self.get_url(domain) for domain in targets]))

    def establish_download_schedule(
        self, max_urls: int = 100, time_limit: int = 10
    ) -> List[str]:
        """Get up to the specified number of URLs along with a suitable
        backoff schedule (in seconds)."""
        # see which domains are free
        with self._lock:
            potential = [d for d in self.urldict if not self.urldict[d].all_visited]
            if not potential:
                self.done = True
                return []
        # variables init
        per_domain = max_urls // len(potential) or 1
        targets: List[Tuple[float, str]] = []
        # iterate potential domains
        for domain in potential:
            url_tuples = self._load_urls(domain)
            # load urls
            urlpaths: List[str] = []
            # get first non-seen urls
            for url in url_tuples:
                if (
                    len(urlpaths) >= per_domain
                    or (len(targets) + len(urlpaths)) >= max_urls
                ):
                    break
                if not url.visited:
                    urlpaths.append(url.urlpath)
                    url.visited = True
                    with self._lock:
                        self.urldict[domain].count += 1
            # determine timestamps
            now = datetime.now()
            original_timestamp = self._timestamp(domain)
            if (
                original_timestamp is None
                or (now - original_timestamp).total_seconds() > time_limit
            ):
                schedule_secs = 0.0
            else:
                schedule_secs = time_limit - float(
                    f"{(now - original_timestamp).total_seconds():.2f}"
                )
            for urlpath in urlpaths:
                targets.append((schedule_secs, domain + urlpath))
                schedule_secs += time_limit
            # calculate difference and offset last addition
            total_diff = now + timedelta(0, schedule_secs - time_limit)
            # store new info
            self._store_urls(domain, url_tuples, timestamp=total_diff)
        # sort by first tuple element (time in secs)
        return sorted(targets, key=lambda x: x[0])  # type: ignore[arg-type]

    def get_rules(self, website: str) -> Optional[RobotFileParser]:
        "Return the stored crawling rules for the given website."
        return self.urldict[website].rules

    # GENERAL INFO

    def total_url_number(self) -> int:
        "Find number of all URLs in store."
        return sum(len(self.urldict[d].tuples) for d in self.urldict)

    def download_threshold_reached(self, threshold: float) -> bool:
        "Find out if the download limit (in seconds) has been reached for one of the websites in store."
        return any(self.urldict[d].count >= threshold for d in self.urldict)

    def dump_urls(self) -> List[str]:
        "Return a list of all known URLs."
        urls = []
        for domain in self.get_known_domains():
            urls.extend(self.find_known_urls(domain))
        return urls

    def print_urls(self) -> None:
        "Print all URLs in store (URL + TAB + visited or not)."
        for domain in self.get_known_domains():
            print(
                "\n".join(
                    [
                        domain + u.urlpath + "\t" + str(u.visited)
                        for u in self._load_urls(domain)
                    ]
                )
            )
