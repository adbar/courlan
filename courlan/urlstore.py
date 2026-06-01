"""
Defines a URL store which holds URLs along with relevant information and entails crawling helpers.
"""

import gc
import logging
import pickle
import signal
import sys

try:
    import bz2

    HAS_BZ2 = True
except ImportError:
    HAS_BZ2 = False

try:
    import zlib

    HAS_ZLIB = True
except ImportError:
    HAS_ZLIB = False


from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from operator import itemgetter
from threading import Lock
from typing import Any
from urllib.robotparser import RobotFileParser

from .clean import normalize_url
from .core import filter_links
from .filters import lang_filter, validate_url
from .meta import clear_caches
from .urlutils import get_base_url, get_host_and_path, is_known_link

LOGGER = logging.getLogger(__name__)


class Compressor:
    "Use system information on available compression modules and define corresponding methods."

    __slots__ = ("compressor", "decompressor")

    def __init__(self, compression: bool = True) -> None:
        self.compressor: Callable[[bytes], bytes]
        self.decompressor: Callable[[bytes], bytes]
        if compression and HAS_BZ2:
            self.compressor, self.decompressor = bz2.compress, bz2.decompress
        elif compression and HAS_ZLIB:
            self.compressor, self.decompressor = zlib.compress, zlib.decompress
        else:
            self.compressor = self.decompressor = self._identical

    @staticmethod
    def _identical(data: Any) -> Any:
        "Return unchanged data."
        return data

    def compress(self, data: Any) -> Any:
        "Pickle the data and compress it if a method is available."
        return self.compressor(pickle.dumps(data, protocol=5))

    def decompress(self, data: bytes) -> Any:
        "Decompress the data if a method is available and load the object."
        return pickle.loads(self.decompressor(data))


COMPRESSOR = Compressor()


class State(Enum):
    "Record state information about a domain or host."

    OPEN = 1
    ALL_VISITED = 2
    BUSTED = 3


class DomainEntry:
    "Class to record host-related information and URL paths."

    __slots__ = ("count", "rules", "state", "timestamp", "total", "tuples")

    def __init__(self, state: State = State.OPEN) -> None:
        self.count: int = 0
        self.rules: RobotFileParser | None = None
        self.state: State = state
        self.timestamp: datetime | None = None
        self.total: int = 0
        self.tuples: deque[UrlPathTuple] = deque()


class UrlPathTuple:
    "Class storing information for URL paths relative to a domain/host."

    __slots__ = ("urlpath", "visited")

    def __init__(self, urlpath: str, visited: bool) -> None:
        self.urlpath: bytes = urlpath.encode("utf-8")
        self.visited: bool = visited

    def path(self) -> str:
        "Get the URL path as string."
        return self.urlpath.decode("utf-8")


class UrlStore:
    "Defines a class to store domain-classified URLs and perform checks against it."

    __slots__ = (
        "compressed",
        "done",
        "language",
        "strict",
        "trailing_slash",
        "urldict",
        "_lock",
    )

    def __init__(
        self,
        compressed: bool = False,
        language: str | None = None,
        strict: bool = False,
        trailing_slash: bool = True,
        verbose: bool = False,
    ) -> None:
        self.compressed: bool = compressed
        self.done: bool = False
        self.language: str | None = language
        self.strict: bool = strict
        self.trailing_slash: bool = trailing_slash
        self.urldict: defaultdict[str, DomainEntry] = defaultdict(DomainEntry)
        self._lock: Lock = Lock()

        def dump_unvisited_urls(num: Any, frame: Any) -> None:
            LOGGER.debug(
                "Processing interrupted, dumping unvisited URLs from %s hosts",
                len(self.urldict),
            )
            self.print_unvisited_urls()
            sys.exit(1)

        # don't use the following on Windows
        if verbose and not sys.platform.startswith("win"):
            try:
                signal.signal(signal.SIGINT, dump_unvisited_urls)
                signal.signal(signal.SIGTERM, dump_unvisited_urls)
            except ValueError:
                # signal handlers can only be registered in the main thread
                LOGGER.warning("Cannot set signal handlers outside the main thread")

    def __getstate__(self) -> dict[str, Any]:
        "Return the picklable state, excluding the unpicklable lock."
        return {slot: getattr(self, slot) for slot in self.__slots__ if slot != "_lock"}

    def __setstate__(self, state: dict[str, Any]) -> None:
        "Restore state after unpickling and re-create the lock."
        for slot, value in state.items():
            setattr(self, slot, value)
        self._lock = Lock()

    def _buffer_urls(
        self, data: list[str], visited: bool = False
    ) -> defaultdict[str, deque[UrlPathTuple]]:
        inputdict: defaultdict[str, deque[UrlPathTuple]] = defaultdict(deque)
        for url in dict.fromkeys(data):
            # segment URL and add to domain dictionary
            try:
                # validate
                validation_result, parsed_url = validate_url(url)
                if validation_result is False or parsed_url is None:
                    LOGGER.debug("Invalid URL: %s", url)
                    raise ValueError
                # filter
                if (
                    self.language is not None
                    and lang_filter(
                        url, self.language, self.strict, self.trailing_slash
                    )
                    is False
                ):
                    LOGGER.debug("Wrong language: %s", url)
                    raise ValueError
                normalized = normalize_url(
                    parsed_url,
                    strict=self.strict,
                    language=self.language,
                    trailing_slash=self.trailing_slash,
                )
                hostinfo, urlpath = get_host_and_path(normalized)
                inputdict[hostinfo].append(UrlPathTuple(urlpath, visited))
            except (TypeError, ValueError):
                LOGGER.warning("Discarding URL: %s", url)
        return inputdict

    def _load_urls(self, domain: str) -> deque[UrlPathTuple]:
        if domain in self.urldict:
            if self.compressed:
                return COMPRESSOR.decompress(self.urldict[domain].tuples)  # type: ignore
            return self.urldict[domain].tuples
        return deque()

    def _set_done(self) -> None:
        if not self.done and all(v.state != State.OPEN for v in self.urldict.values()):
            with self._lock:
                self.done = True

    def _store_urls(
        self,
        domain: str,
        to_right: deque[UrlPathTuple] | None = None,
        timestamp: datetime | None = None,
        to_left: deque[UrlPathTuple] | None = None,
    ) -> None:
        # http/https switch
        if domain.startswith("http://"):
            candidate = "https" + domain[4:]
            # switch
            if candidate in self.urldict:
                domain = candidate
        elif domain.startswith("https://"):
            candidate = "http" + domain[5:]
            # replace entry
            if candidate in self.urldict:
                self.urldict[domain] = self.urldict[candidate]
                del self.urldict[candidate]

        # load URLs or create entry
        if domain in self.urldict:
            # discard if busted
            if self.urldict[domain].state is State.BUSTED:
                return
            urls = self._load_urls(domain)
            known = {u.path() for u in urls}
        else:
            urls = deque()
            known = set()

        # check if the link or its variants are known
        if to_right is not None:
            urls.extend(t for t in to_right if not is_known_link(t.path(), known))
        if to_left is not None:
            urls.extendleft(t for t in to_left if not is_known_link(t.path(), known))

        with self._lock:
            if self.compressed:
                self.urldict[domain].tuples = COMPRESSOR.compress(urls)
            else:
                self.urldict[domain].tuples = urls
            self.urldict[domain].total = len(urls)

            if timestamp is not None:
                self.urldict[domain].timestamp = timestamp

            if all(u.visited for u in urls):
                self.urldict[domain].state = State.ALL_VISITED
            else:
                self.urldict[domain].state = State.OPEN
                if self.done:
                    self.done = False

    def _search_urls(self, urls: list[str], switch: int | None = None) -> list[str]:
        # init
        last_domain: str | None = None
        known_paths: dict[str, bool | None] = {}
        remaining_urls = dict.fromkeys(urls)
        # iterate
        for url in sorted(remaining_urls):
            hostinfo, urlpath = get_host_and_path(url)
            # examine domain
            if hostinfo != last_domain:
                last_domain = hostinfo
                known_paths = {u.path(): u.visited for u in self._load_urls(hostinfo)}
            # run checks: case 1: the path matches, case 2: visited URL
            if urlpath in known_paths and (
                switch == 1 or (switch == 2 and known_paths[urlpath])
            ):
                del remaining_urls[url]
        # preserve input order
        return list(remaining_urls)

    # ADDITIONS AND DELETIONS

    def add_urls(
        self,
        urls: list[str] | None = None,
        appendleft: list[str] | None = None,
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

    def add_from_html(
        self,
        htmlstring: str,
        url: str,
        external: bool = False,
        lang: str | None = None,
        with_nav: bool = True,
    ) -> None:
        "Find links in a HTML document, filter them and add them to the data store."
        # lang = lang or self.language
        base_url = get_base_url(url)
        rules = self.get_rules(base_url)
        links, links_priority = filter_links(
            htmlstring=htmlstring,
            url=url,
            external=external,
            lang=lang or self.language,
            rules=rules,
            strict=self.strict,
            with_nav=with_nav,
        )
        self.add_urls(urls=links, appendleft=links_priority)

    def discard(self, domains: list[str]) -> None:
        "Declare domains void and prune the store."
        with self._lock:
            for d in domains:
                self.urldict[d] = DomainEntry(state=State.BUSTED)
        self._set_done()
        num = gc.collect()
        LOGGER.debug("%s objects in GC after UrlStore.discard", num)

    def reset(self) -> None:
        "Re-initialize the URL store."
        with self._lock:
            self.urldict = defaultdict(DomainEntry)
        clear_caches()
        num = gc.collect()
        LOGGER.debug("UrlStore reset, %s objects in GC", num)

    # DOMAINS / HOSTNAMES

    def get_known_domains(self) -> list[str]:
        "Return all known domains as a list."
        return list(self.urldict.keys())

    def get_unvisited_domains(self) -> list[str]:
        """Find all domains for which there are unvisited URLs
        and potentially adjust done meta-information."""
        return [d for d, v in self.urldict.items() if v.state == State.OPEN]

    def is_exhausted_domain(self, domain: str) -> bool:
        "Tell if all known URLs for the website have been visited."
        if domain in self.urldict:
            return self.urldict[domain].state != State.OPEN
        return False
        # raise KeyError("website not in store")

    def unvisited_websites_number(self) -> int:
        "Return the number of websites for which there are still URLs to visit."
        return len(self.get_unvisited_domains())

    # URL-BASED QUERIES

    def find_known_urls(self, domain: str) -> list[str]:
        """Get all already known URLs for the given domain (ex. "https://example.org")."""
        return [domain + u.path() for u in self._load_urls(domain)]

    def find_unvisited_urls(self, domain: str) -> list[str]:
        "Get all unvisited URLs for the given domain."
        if not self.is_exhausted_domain(domain):
            return [domain + u.path() for u in self._load_urls(domain) if not u.visited]
        return []

    def filter_unknown_urls(self, urls: list[str]) -> list[str]:
        "Take a list of URLs and return the currently unknown ones."
        return self._search_urls(urls, switch=1)

    def filter_unvisited_urls(self, urls: list[str]) -> list[str]:
        "Take a list of URLs and return the currently unvisited ones."
        return self._search_urls(urls, switch=2)

    def has_been_visited(self, url: str) -> bool:
        "Check if the given URL has already been visited."
        return not bool(self.filter_unvisited_urls([url]))

    def is_known(self, url: str) -> bool:
        "Check if the given URL has already been stored."
        hostinfo, urlpath = get_host_and_path(url)
        # returns False if domain or URL is new
        return urlpath in {u.path() for u in self._load_urls(hostinfo)}

    # DOWNLOADS

    def get_url(self, domain: str, as_visited: bool = True) -> str | None:
        "Retrieve a single URL and consider it to be visited (with corresponding timestamp)."
        # not fully used
        if not self.is_exhausted_domain(domain):
            url_tuples = self._load_urls(domain)
            # get first non-seen url
            for url in url_tuples:
                if not url.visited:
                    # store information
                    if as_visited:
                        url.visited = True
                        with self._lock:
                            self.urldict[domain].count += 1
                        self._store_urls(domain, url_tuples, timestamp=datetime.now())
                    return domain + url.path()
        # nothing to draw from
        with self._lock:
            self.urldict[domain].state = State.ALL_VISITED
        self._set_done()
        return None

    def get_download_urls(
        self,
        time_limit: float = 10.0,
        max_urls: int = 10000,
    ) -> list[str]:
        """Get a list of immediately downloadable URLs according to the given
        time limit per domain."""
        urls = []
        for website, entry in self.urldict.items():
            if entry.state != State.OPEN:
                continue
            if (
                not entry.timestamp
                or (datetime.now() - entry.timestamp).total_seconds() > time_limit
            ):
                url = self.get_url(website)
                if url is not None:
                    urls.append(url)
                    if len(urls) >= max_urls:
                        break
        self._set_done()
        return urls

    def establish_download_schedule(
        self, max_urls: int = 100, time_limit: int = 10
    ) -> list[str]:
        """Get up to the specified number of URLs along with a suitable
        backoff schedule (in seconds)."""
        # see which domains are free
        potential = self.get_unvisited_domains()
        if not potential:
            return []
        # variables init
        per_domain = max_urls // len(potential) or 1
        targets: list[tuple[float, str]] = []
        # iterate potential domains
        for domain in potential:
            # load urls
            url_tuples = self._load_urls(domain)
            urlpaths: list[str] = []
            # get first non-seen urls
            for url in url_tuples:
                if (
                    len(urlpaths) >= per_domain
                    or (len(targets) + len(urlpaths)) >= max_urls
                ):
                    break
                if not url.visited:
                    urlpaths.append(url.path())
                    url.visited = True
                    with self._lock:
                        self.urldict[domain].count += 1
            # determine timestamps
            now = datetime.now()
            original_timestamp = self.urldict[domain].timestamp
            if (
                not original_timestamp
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
        self._set_done()
        return sorted(targets, key=itemgetter(1))  # type: ignore[arg-type]

    # CRAWLING

    def store_rules(self, website: str, rules: RobotFileParser | None) -> None:
        "Store crawling rules for a given website."
        if self.compressed:
            rules = COMPRESSOR.compress(rules)
        self.urldict[website].rules = rules

    def get_rules(self, website: str) -> RobotFileParser | None:
        "Return the stored crawling rules for the given website."
        if website in self.urldict:
            if self.compressed:
                return COMPRESSOR.decompress(self.urldict[website].rules)  # type: ignore
            return self.urldict[website].rules
        return None

    def get_crawl_delay(self, website: str, default: float = 5) -> float:
        "Return the delay as extracted from robots.txt, or a given default."
        delay = None
        rules = self.get_rules(website)
        try:
            delay = rules.crawl_delay("*")  # type: ignore[union-attr]
        except AttributeError:  # no rules or no crawl delay
            pass
        # backup
        return delay or default  # type: ignore[return-value]

    # GENERAL INFO

    def get_all_counts(self) -> list[int]:
        "Return all download counts for the hosts in store."
        return [v.count for v in self.urldict.values()]

    def total_url_number(self) -> int:
        "Find number of all URLs in store."
        return sum(v.total for v in self.urldict.values())

    def download_threshold_reached(self, threshold: float) -> bool:
        "Find out if the download limit (in seconds) has been reached for one of the websites in store."
        return any(v.count >= threshold for v in self.urldict.values())

    def dump_urls(self) -> list[str]:
        "Return a list of all known URLs."
        urls = []
        for domain in self.urldict:
            urls.extend(self.find_known_urls(domain))
        return urls

    def print_unvisited_urls(self) -> None:
        "Print all unvisited URLs in store."
        for domain in self.urldict:
            print("\n".join(self.find_unvisited_urls(domain)), flush=True)

    def print_urls(self) -> None:
        "Print all URLs in store (URL + TAB + visited or not)."
        for domain in self.urldict:
            print(
                "\n".join(
                    [
                        f"{domain}{u.path()}\t{str(u.visited)}"
                        for u in self._load_urls(domain)
                    ]
                ),
                flush=True,
            )

    # PERSISTANCE

    def write(self, filename: str) -> None:
        "Write the URL store to disk."
        with open(filename, "wb") as output:
            pickle.dump(self, output)


def load_store(filename: str) -> UrlStore:
    "Load a URL store from disk."
    with open(filename, "rb") as output:
        url_store = pickle.load(output)
    return url_store
