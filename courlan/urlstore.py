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
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from enum import Enum
from itertools import islice
from operator import itemgetter
from threading import Lock
from typing import Any
from urllib.robotparser import RobotFileParser

from .clean import normalize_and_split, normalize_netloc_parts
from .core import filter_links
from .filters import lang_filter, validate_url
from .hosts import _unicode_host
from .meta import clear_caches
from .urlutils import _parse, _slash_variant, _swap_scheme, get_base_url

LOGGER = logging.getLogger(__name__)


def _decompress(data: bytes) -> bytes:
    "Decompress by magic bytes, stores written with bz2 included."
    if data[:3] == b"BZh" and HAS_BZ2:
        return bz2.decompress(data)
    if data[:1] == b"\x78" and HAS_ZLIB:
        return zlib.decompress(data)
    return data


class Compressor:
    "Use system information on available compression modules and define corresponding methods."

    __slots__ = ("compressor", "decompressor")

    def __init__(self, compression: bool = True) -> None:
        self.compressor: Callable[[bytes], bytes]
        # pickles start with b"\x80", never with a compression magic byte
        self.decompressor: Callable[[bytes], bytes] = _decompress
        if compression and HAS_ZLIB:
            self.compressor = zlib.compress
        elif compression and HAS_BZ2:
            self.compressor = bz2.compress
        else:
            self.compressor = self._identical

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

    __slots__ = ("count", "cursor", "rules", "state", "timestamp", "total", "tuples")

    def __init__(self, state: State = State.OPEN) -> None:
        self.count: int = 0
        # all URLs before the cursor are visited
        self.cursor: int = 0
        self.rules: bytes | RobotFileParser | None = None
        self.state: State = state
        self.timestamp: datetime | None = None
        self.total: int = 0
        self.tuples: bytes | deque[UrlPathTuple] = deque()

    def __setstate__(self, state: tuple[None, dict[str, Any]]) -> None:
        "Fill in the slots missing from older pickles."
        self.__init__()  # type: ignore[misc]
        for slot, value in state[1].items():
            setattr(self, slot, value)


class UrlPathTuple:
    "Class storing information for URL paths relative to a domain/host."

    __slots__ = ("urlpath", "visited")

    def __init__(self, urlpath: str, visited: bool) -> None:
        self.urlpath: bytes = urlpath.encode("utf-8")
        self.visited: bool = visited

    def path(self) -> str:
        "Get the URL path as string."
        return self.urlpath.decode("utf-8")


PathIndex = dict[str, UrlPathTuple]


def _host_key(domain: str) -> str:
    "Return the store key of a domain or URL: normalized scheme and host, no userinfo or path."
    parsed = _parse(domain)
    if not parsed.netloc:
        return domain
    scheme, _, hostport = normalize_netloc_parts(parsed)
    return f"{scheme}://{_unicode_host(hostport)}"


def _lookup(path: str, index: PathIndex) -> UrlPathTuple | None:
    "Find the stored tuple for a path or its trailing slash variant."
    return index.get(path) or index.get(_slash_variant(path))


def _first_unvisited(urls: deque[UrlPathTuple], start: int) -> int:
    "Return the index of the first unvisited URL from start on, len(urls) if none."
    if start < len(urls) and not urls[start].visited:
        return start
    return next(
        (i for i, u in enumerate(islice(urls, start, None), start) if not u.visited),
        len(urls),
    )


def _dedup_extend(
    urls: deque[UrlPathTuple],
    index: PathIndex,
    tuples: Iterable[UrlPathTuple],
    left: bool = False,
) -> int:
    """Add tuples whose paths are not yet known, in input order, and return their number.
    A visited input marks the stored URL as visited, never the reverse."""
    new = []
    for utuple in tuples:
        path = utuple.path()
        known = _lookup(path, index)
        if known is None:
            new.append(utuple)
            index[path] = utuple
        elif utuple.visited:
            known.visited = True
    if left:
        urls.extendleft(reversed(new))
    else:
        urls.extend(new)
    return len(new)


class UrlStore:
    """Defines a class to store domain-classified URLs and perform checks against it.

    Domains are keyed in normalized form: lowercase, unicode host, no userinfo
    or default port, under https if both twins are known. Readers accept any form.

    Thread-safety: readers are safe and writers are serialized, but a logical
    write is not globally atomic — drive mutations from a single writer thread."""

    __slots__ = (
        "compressed",
        "done",
        "language",
        "strict",
        "trailing_slash",
        "urldict",
        "_hot",
        "_index",
        "_lock",
        "_offset",
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
        self.urldict: dict[str, DomainEntry] = {}
        # last written domain with its uncompressed deque, and its path index
        self._hot: tuple[DomainEntry, deque[UrlPathTuple]] | None = None
        self._index: PathIndex | None = None
        self._lock: Lock = Lock()
        # rotating start of get_download_urls
        self._offset: int = 0

        def dump_unvisited_urls(num: Any, frame: Any) -> None:
            LOGGER.debug(
                "Processing interrupted, dumping unvisited URLs from %s hosts",
                len(self.urldict),
            )
            self.print_unvisited_urls()
            sys.exit(1)

        # opt-in only (mostly for CLI use), and not on Windows:
        # existing handlers are replaced since the caller asked for it
        if verbose and not sys.platform.startswith("win"):
            try:
                signal.signal(signal.SIGINT, dump_unvisited_urls)
                signal.signal(signal.SIGTERM, dump_unvisited_urls)
            except ValueError:
                # signal handlers can only be registered in the main thread
                LOGGER.warning("Cannot set signal handlers outside the main thread")

    def __getstate__(self) -> dict[str, Any]:
        "Return the picklable state, excluding the lock and the hot domain."
        self._freeze()
        return {
            slot: getattr(self, slot)
            for slot in self.__slots__
            if slot not in ("_hot", "_index", "_lock")
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        "Restore state after unpickling, older stores included."
        self._hot = self._index = None
        self._lock = Lock()
        self._offset = 0
        for slot, value in state.items():
            setattr(self, slot, value)
        # older stores use a defaultdict, whose reads create entries
        self.urldict = dict(self.urldict)

    def _split(self, url: str) -> tuple[str, str, str] | None:
        "Return the normalized URL, the store key and the path, None if the URL is invalid."
        _, parsed_url = validate_url(url)
        if parsed_url is None:
            return None
        try:
            normalized, base, urlpath = normalize_and_split(
                parsed_url, self.strict, self.language, self.trailing_slash
            )
        except ValueError:
            return None
        # the base is already normalized apart from these two
        if "@" in base or "xn--" in base:
            base = _host_key(base)
        return normalized, base, urlpath

    def _buffer_urls(
        self, data: list[str], visited: bool
    ) -> defaultdict[str, deque[UrlPathTuple]]:
        inputdict: defaultdict[str, deque[UrlPathTuple]] = defaultdict(deque)
        for url in dict.fromkeys(data):
            split = self._split(url)
            # filter on the final form, as in check_url
            if split is None or (
                self.language is not None
                and lang_filter(
                    split[0], self.language, self.strict, self.trailing_slash
                )
                is False
            ):
                LOGGER.warning("Discarding URL: %s", url)
                continue
            inputdict[split[1]].append(UrlPathTuple(split[2], visited))
        return inputdict

    def _find(self, key: str) -> str | None:
        "Return the stored key for a normalized key or its http/https twin."
        if key in self.urldict:
            return key
        if (
            key.startswith(("http://", "https://"))
            and (twin := _swap_scheme(key)) in self.urldict
        ):
            return twin
        return None

    def _load_urls(self, domain: str) -> deque[UrlPathTuple]:
        raw = self.urldict[domain].tuples
        if isinstance(raw, bytes):  # compressed
            result: deque[UrlPathTuple] = COMPRESSOR.decompress(raw)
            return result
        return raw

    def _is_hot(self, entry: DomainEntry) -> bool:
        return (
            self._hot is not None
            and self._hot[0] is entry
            and entry.tuples is self._hot[1]
        )

    def _paths(self, key: str) -> PathIndex:
        "Return the path index of a stored domain, kept for the hot one."
        if self._is_hot(self.urldict[key]) or not self.compressed:
            self._live(key)
            return self._hot_index()
        return {u.path(): u for u in self._load_urls(key)}

    def _hot_index(self) -> PathIndex:
        "Return the path index of the hot domain, built on first use."
        if self._index is None:
            assert self._hot is not None
            self._index = {u.path(): u for u in self._hot[1]}
        return self._index

    def _freeze(self) -> None:
        "Compress the hot domain again and drop its index."
        if self._hot is not None:
            entry, urls = self._hot
            if self.compressed and entry.tuples is urls:
                entry.tuples = COMPRESSOR.compress(urls)
            self._hot = self._index = None

    def _live(self, key: str) -> deque[UrlPathTuple]:
        """Return the deque of a stored domain for writing.
        In compressed mode it stays uncompressed until another domain is written."""
        entry = self.urldict[key]
        if self._hot is None or not self._is_hot(entry):
            self._freeze()
            entry.tuples = urls = self._load_urls(key)
            self._hot = (entry, urls)
        return self._hot[1]

    def _update(self, entry: DomainEntry, urls: deque[UrlPathTuple]) -> None:
        "Refresh the counters and the state of an entry after a write."
        entry.total = len(urls)
        entry.cursor = _first_unvisited(urls, entry.cursor)
        if entry.cursor < len(urls):
            entry.state = State.OPEN
            self.done = False
        else:
            entry.state = State.ALL_VISITED

    def _set_done(self) -> None:
        if not self.done and all(v.state != State.OPEN for v in self.urldict.values()):
            with self._lock:
                self.done = True

    def _merge_entries(self, target: str, source: str) -> None:
        "Merge the source entry into the target one; a discarded twin voids the domain."
        tgt, src = self.urldict[target], self.urldict[source]
        if State.BUSTED in (tgt.state, src.state):
            self.urldict[target] = DomainEntry(state=State.BUSTED)
            return
        urls = self._live(target)
        index = self._hot_index()
        _dedup_extend(urls, index, self._load_urls(source))
        tgt.count += src.count
        if tgt.rules is None:
            tgt.rules = src.rules
        if src.timestamp and (not tgt.timestamp or src.timestamp > tgt.timestamp):
            tgt.timestamp = src.timestamp
        tgt.cursor = 0
        self._update(tgt, urls)

    def _merge_twin(self, domain: str) -> str:
        """Canonicalize the domain under the https key if a twin exists,
        merging coexisting entries into a single one."""
        if not domain.startswith(("http://", "https://")):
            return domain
        https_key = domain if domain.startswith("https://") else _swap_scheme(domain)
        http_key = _swap_scheme(https_key)
        # check-and-swap must be atomic against other writers
        with self._lock:
            if https_key in self.urldict:
                if http_key in self.urldict:
                    self._merge_entries(https_key, http_key)
                    del self.urldict[http_key]
                return https_key
            if domain == https_key and http_key in self.urldict:
                # upgrade the existing http entry to the https key
                self.urldict[https_key] = self.urldict.pop(http_key)
                return https_key
        return domain

    def _store_urls(
        self,
        domain: str,
        to_right: deque[UrlPathTuple] | None = None,
        to_left: deque[UrlPathTuple] | None = None,
    ) -> None:
        domain = self._merge_twin(domain)
        if domain not in self.urldict:
            with self._lock:
                self.urldict[domain] = DomainEntry()
        entry = self.urldict[domain]
        if entry.state is State.BUSTED:
            return
        urls = self._live(domain)
        index = self._hot_index()
        if to_right is not None:
            _dedup_extend(urls, index, to_right)
        if to_left is not None and _dedup_extend(urls, index, to_left, left=True):
            entry.cursor = 0
        with self._lock:
            self._update(entry, urls)

    def _search_urls(self, urls: list[str], switch: int | None = None) -> list[str]:
        "Return the URLs not stored (switch 1) or not visited (switch 2), in input order."
        remaining = []
        indexes: dict[str, PathIndex] = {}
        for url in dict.fromkeys(urls):
            split = self._split(url)
            key = self._find(split[1]) if split else None
            if split and key:
                if key not in indexes:
                    indexes[key] = self._paths(key)
                known = _lookup(split[2], indexes[key])
                # case 1: the path matches, case 2: visited URL
                if known and (switch == 1 or (switch == 2 and known.visited)):
                    continue
            remaining.append(url)
        return remaining

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
        "Declare domains void and prune the store, http/https twins included."
        for domain in domains:
            domain = self._merge_twin(_host_key(domain))
            with self._lock:
                self.urldict[domain] = DomainEntry(state=State.BUSTED)
        self._set_done()
        num = gc.collect()
        LOGGER.debug("%s objects in GC after UrlStore.discard", num)

    def reset(self) -> None:
        "Re-initialize the URL store."
        with self._lock:
            self.urldict = {}
            self._hot = self._index = None
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
        key = self._find(_host_key(domain))
        return key is not None and self.urldict[key].state != State.OPEN

    def unvisited_websites_number(self) -> int:
        "Return the number of websites for which there are still URLs to visit."
        return len(self.get_unvisited_domains())

    # URL-BASED QUERIES

    def find_known_urls(self, domain: str) -> list[str]:
        """Get all already known URLs for the given domain (ex. "https://example.org")."""
        key = self._find(_host_key(domain))
        return [key + u.path() for u in self._load_urls(key)] if key else []

    def find_unvisited_urls(self, domain: str) -> list[str]:
        "Get all unvisited URLs for the given domain."
        key = self._find(_host_key(domain))
        return self._unvisited(key) if key else []

    def _unvisited(self, key: str) -> list[str]:
        if self.urldict[key].state is not State.OPEN:
            return []
        return [key + u.path() for u in self._load_urls(key) if not u.visited]

    def filter_unknown_urls(self, urls: list[str]) -> list[str]:
        "Take a list of URLs and return the currently unknown ones."
        return self._search_urls(urls, switch=1)

    def filter_unvisited_urls(self, urls: list[str]) -> list[str]:
        "Take a list of URLs and return the currently unvisited ones."
        return self._search_urls(urls, switch=2)

    def has_been_visited(self, url: str) -> bool:
        "Check if the given URL has already been visited."
        return not self.filter_unvisited_urls([url])

    def is_known(self, url: str) -> bool:
        "Check if the given URL has already been stored."
        return not self.filter_unknown_urls([url])

    # DOWNLOADS

    def get_url(self, domain: str, as_visited: bool = True) -> str | None:
        "Retrieve a single URL and consider it to be visited (with corresponding timestamp)."
        # merge any twin first so the writes below stay on one key
        domain = self._merge_twin(_host_key(domain))
        entry = self.urldict.get(domain)
        if entry is None:
            return None
        if entry.state is State.OPEN:
            urls = self._live(domain)
            i = _first_unvisited(urls, entry.cursor)
            if i < len(urls):
                url = urls[i]
                if as_visited:
                    url.visited = True
                    with self._lock:
                        entry.count += 1
                        entry.timestamp = datetime.now()
                        self._update(entry, urls)
                return domain + url.path()
            # nothing to draw from, a discarded domain stays so
            with self._lock:
                entry.state = State.ALL_VISITED
        self._set_done()
        return None

    def get_download_urls(
        self,
        time_limit: float = 10.0,
        max_urls: int = 10000,
    ) -> list[str]:
        """Get a list of immediately downloadable URLs according to the given
        time limit per domain. Each call starts after the last domain served."""
        urls: list[str] = []
        # snapshot the keys: get_url may merge twin entries and mutate the dict
        websites = list(self.urldict)
        start = self._offset % len(websites) if websites else 0
        for position, website in enumerate(websites[start:] + websites[:start], start):
            entry = self.urldict.get(website)
            if entry is None or entry.state != State.OPEN:
                continue
            if (
                not entry.timestamp
                or (datetime.now() - entry.timestamp).total_seconds() > time_limit
            ):
                url = self.get_url(website)
                if url is not None:
                    urls.append(url)
                    if len(urls) >= max_urls:
                        self._offset = position + 1
                        break
        self._set_done()
        return urls

    def establish_download_schedule(
        self, max_urls: int = 100, time_limit: int = 10
    ) -> list[tuple[float, str]]:
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
            if len(targets) >= max_urls:
                break
            # merge any twin first so the writes below stay on one key
            domain = self._merge_twin(domain)
            entry = self.urldict[domain]
            urls = self._live(domain)
            urlpaths: list[str] = []
            # get first non-seen urls
            i = entry.cursor
            while (
                len(urlpaths) < per_domain and len(targets) + len(urlpaths) < max_urls
            ):
                i = _first_unvisited(urls, i)
                if i == len(urls):
                    break
                urls[i].visited = True
                urlpaths.append(urls[i].path())
                i += 1
            # determine timestamps
            now = datetime.now()
            original_timestamp = entry.timestamp
            if (
                not original_timestamp
                or (now - original_timestamp).total_seconds() > time_limit
            ):
                schedule_secs = 0.0
            else:
                schedule_secs = time_limit - round(
                    (now - original_timestamp).total_seconds(), 2
                )
            for urlpath in urlpaths:
                targets.append((schedule_secs, domain + urlpath))
                schedule_secs += time_limit
            # store new info, offset of the last addition
            with self._lock:
                entry.count += len(urlpaths)
                entry.timestamp = now + timedelta(0, schedule_secs - time_limit)
                self._update(entry, urls)
        # sort by first tuple element (time in secs)
        self._set_done()
        return sorted(targets, key=itemgetter(0))

    # CRAWLING

    def store_rules(self, website: str, rules: RobotFileParser | None) -> None:
        "Store crawling rules for a given website."
        website = self._merge_twin(_host_key(website))
        if self.compressed:
            rules = COMPRESSOR.compress(rules)
        with self._lock:
            if website not in self.urldict:
                # rules alone leave nothing to visit
                self.urldict[website] = DomainEntry(state=State.ALL_VISITED)
            self.urldict[website].rules = rules

    def get_rules(self, website: str) -> RobotFileParser | None:
        "Return the stored crawling rules for the given website."
        key = self._find(_host_key(website))
        if key is None:
            return None
        raw = self.urldict[key].rules
        if isinstance(raw, bytes):  # compressed
            result: RobotFileParser = COMPRESSOR.decompress(raw)
            return result
        return raw

    def get_crawl_delay(self, website: str, default: float = 5) -> float:
        "Return the delay as extracted from robots.txt, or a given default."
        rules = self.get_rules(website)
        if rules is None:
            return default
        delay = rules.crawl_delay("*")
        return float(delay) if delay is not None else default

    # GENERAL INFO

    def get_all_counts(self) -> list[int]:
        "Return all download counts for the hosts in store."
        return [v.count for v in self.urldict.values()]

    def total_url_number(self) -> int:
        "Find number of all URLs in store."
        return sum(v.total for v in self.urldict.values())

    def download_threshold_reached(self, threshold: float) -> bool:
        "Find out if the download threshold (number of retrieved URLs) has been reached for one of the websites in store."
        return any(v.count >= threshold for v in self.urldict.values())

    def dump_urls(self) -> list[str]:
        "Return a list of all known URLs."
        return [d + u.path() for d in self.urldict for u in self._load_urls(d)]

    def print_unvisited_urls(self) -> None:
        "Print all unvisited URLs in store."
        for domain in self.urldict:
            if urls := self._unvisited(domain):
                print("\n".join(urls), flush=True)

    def print_urls(self) -> None:
        "Print all URLs in store (URL + TAB + visited or not)."
        for domain in self.urldict:
            if urls := [
                f"{domain}{u.path()}\t{u.visited!s}" for u in self._load_urls(domain)
            ]:
                print("\n".join(urls), flush=True)

    # PERSISTENCE

    def write(self, filename: str) -> None:
        "Write the URL store to disk as a pickle file, see load_store()."
        with open(filename, "wb") as output:
            pickle.dump(self, output)


def load_store(filename: str) -> UrlStore:
    """Load a URL store from disk.

    Warning: uses pickle, which can execute arbitrary code.
    Only load files you have written yourself with UrlStore.write()."""
    with open(filename, "rb") as output:
        url_store: UrlStore = pickle.load(output)
    return url_store
