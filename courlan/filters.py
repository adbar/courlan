"""
Bundles functions needed to target text content and validate the input.
"""

import logging
import re
from urllib.parse import SplitResult, urlsplit

from .hosts import _canonical_ip, _idna_encode
from .langcodes import langcodes_score
from .urlutils import _strip_trailing_dot

LOGGER = logging.getLogger(__name__)


PROTOCOLS = {"http", "https"}

# cheap char gate for IP literals, before the exact _canonical_ip() check
IP_SET = frozenset("0123456789abcdef.:")

# https://github.com/python-validators/validators/blob/master/src/validators/domain.py
VALID_DOMAIN_PORT = re.compile(
    # First character of the domain
    r"^(?:[a-zA-Z0-9]"
    # Sub domain + hostname
    + r"(?:[a-zA-Z0-9-_]{0,61}[A-Za-z0-9])?\.)"
    # First 61 characters of the gTLD
    + r"+[A-Za-z0-9][A-Za-z0-9-_]{0,61}"
    # Last character of the gTLD
    + r"[A-Za-z]"
    # Port number
    + r"(\:(6553[0-5]|655[0-2][0-9]|65[0-4][0-9]{2}|"
    + r"6[0-4][0-9]{3}|[1-5][0-9]{4}|[1-9][0-9]{0,3}))?$",
    re.IGNORECASE,
)

# content filters
# feeds + blogspot, at the end of the path and with any number of slashes
FEED_FILTER = re.compile(r"(?:/(?:feed|rss)|_archive\.html)/*$")
SITE_STRUCTURE = re.compile(
    # wordpress
    r"/(?:wp-(?:admin|content|includes|json|themes)|"
    r"paged?|seite|search|suche|gall?er[a-z]{1,2}|labels|"
    r"archives|uploads|modules|attachment|oembed)/|"
    # wordpress + short URL
    r"[/_-](?:tags?|schlagwort|[ck]ategor[a-z]{1,2}|[ck]at|auth?or|user)/[^/]+/?$|"
    # mixed/blogspot
    r"[^0-9]/[0-9]+/[0-9]+/$|[^0-9]/[0-9]{4}/$",
    re.IGNORECASE,
)
FILE_TYPE = re.compile(
    r"\.(atom|json|css|xml|js|jpg|jpeg|png|svg|gif|tiff|pdf|ogg|mp3|m4a|aac|"
    r"avi|mp4|mov|web[mp]|flv|ico|pls|zip|tar|gz|iso|swf|woff|eot|ttf)\b|"
    r"[/-](img|jpg|png)(\b|_)",
    re.IGNORECASE,
)  # (?=[&?])
ADULT_AND_VIDEOS = re.compile(
    r"[/_-](?:bild-?kontakte|fick|gangbang|incest|live-?cams?|live-?chat|"
    r"porno?|sexcam|sexyeroti[ck]|swinger|x{3})\b",
    re.IGNORECASE,
)

# language filter
PATH_LANG_FILTER = re.compile(
    r"(?:https?://[^/]+/)([a-z]{2})([_-][a-z]{2})?(?:/|$)", re.IGNORECASE
)
# lookahead on the trailing slash so adjacent segments (/en/de/) don't share it
ALL_PATH_LANGS = re.compile(r"/([a-z]{2})([_-][a-z]{2})?(?=/)", re.IGNORECASE)
ALL_PATH_LANGS_NO_TRAILING = re.compile(
    r"/([a-z]{2})([_-][a-z]{2})?(?=/|$)", re.IGNORECASE
)
HOST_LANG_FILTER = re.compile(
    r"https?://([a-z]{2})\.(?:[^.]{4,})\.(?:[^.]+)(?:\.[^.]+)?(?:/|$)", re.IGNORECASE
)

# navigation/crawls
NAVIGATION_FILTER = re.compile(
    r"[/_-](archives|auth?or|[ck]at|category|kategorie|paged?|schlagwort|seite|tags?|topics?|user)/|\?p=[0-9]+",
    re.IGNORECASE,
)
NOTCRAWLABLE = re.compile(
    r"/([ck]onta[ck]t|datenschutzerkl(?:.|%[0-9a-f]{2}){1,2}rung|login|impressum|imprint)(\.[a-z]{3,4})?/?$|/login\?|"
    r"/(javascript:|mailto:|tel\.?:|whatsapp:)",
    re.IGNORECASE,
)
# |/(www\.)?(facebook\.com|google\.com|instagram\.com|twitter\.com)/
INDEX_PAGE_FILTER = re.compile(
    r".{0,5}/(default|home|index)(\.[a-z]{3,5})?/?$", re.IGNORECASE
)

# document types
EXTENSION_REGEX = re.compile(r"\.[a-z]{2,5}$")
# https://en.wikipedia.org/wiki/List_of_file_formats#Web_page
WHITELISTED_EXTENSIONS = {
    ".adp",
    ".amp",
    ".asp",
    ".aspx",
    ".cfm",
    ".cgi",
    ".do",
    ".htm",
    ".html",
    ".htx",
    ".jsp",
    ".mht",
    ".mhtml",
    ".php",
    ".php3",
    ".php4",
    ".php5",
    ".phtml",
    ".pl",
    ".shtml",
    ".stm",
    ".txt",
    ".xhtml",
    ".xml",
}


def basic_filter(url: str) -> bool:
    "Filter URLs based on basic formal characteristics."
    return bool(url.startswith("http") and 10 <= len(url) < 500)


def _valid_port(tail: str) -> bool:
    "Port 1-65535 with no leading zero (mirrors VALID_DOMAIN_PORT's [1-9]... rule)."
    return bool(tail) and tail[:1] != "0" and tail.isdigit() and int(tail) < 65536


def _split_port(value: str) -> tuple[str, str]:
    "Split a trailing valid port off a host, else return the host unchanged."
    host, sep, port = value.rpartition(":")
    return (host, port) if sep and _valid_port(port) else (value, "")


def domain_filter(domain: str) -> bool:
    "Find invalid domain/host names."
    # FQDN absolute form ("example.com.") is valid; extract_domain already strips it
    domain = _strip_trailing_dot(domain)
    # no valid FQDN exceeds the DNS length limit
    if len(domain) > 253:
        return False
    # Bracketed IPv6 netloc from urlsplit: [addr] or [addr]:port
    if domain.startswith("["):
        end = domain.find("]")
        if end == -1:
            return False
        host, rest = domain[1:end], domain[end + 1 :]
        if not _canonical_ip(host):
            return False
        return not rest or (rest.startswith(":") and _valid_port(rest[1:]))
    # IP literal, or IPv4 with a port (a port-bearing host is still all-IP_SET)
    if all(c in IP_SET for c in domain):
        if _canonical_ip(domain):
            return True
        head, port = _split_port(domain)
        if port and _canonical_ip(head):
            return True

    # malformed domains: retry against the punycode form before rejecting
    if not VALID_DOMAIN_PORT.match(domain):
        # the port is not part of the IDNA encoding
        host, port = _split_port(domain)
        try:
            ascii_domain = _idna_encode(host)
        except UnicodeError:
            return False
        if port:
            ascii_domain = f"{ascii_domain}:{port}"
        if not VALID_DOMAIN_PORT.match(ascii_domain):
            return False

    # unsuitable content
    if domain.split(".")[0].isdigit() or FILE_TYPE.search(domain):
        return False

    # extensions
    extension_match = EXTENSION_REGEX.search(domain.lower())
    return not extension_match or extension_match[0] not in WHITELISTED_EXTENSIONS


def extension_filter(urlpath: str) -> bool:
    "Filter based on file extension."
    extension_match = EXTENSION_REGEX.search(urlpath.lower())
    return not extension_match or extension_match[0] in WHITELISTED_EXTENSIONS


def lang_filter(
    url: str,
    language: str | None = None,
    strict: bool = False,
    trailing_slash: bool = True,
) -> bool:
    "Heuristics targeting internationalization and linguistic elements based on a score."
    if language is None:
        return True
    score = 0
    # first test: internationalization cues in the URL path
    if PATH_LANG_FILTER.match(url):
        regex = ALL_PATH_LANGS if trailing_slash else ALL_PATH_LANGS_NO_TRAILING
        occurrences = regex.findall(url)
        # skip if there are too many candidates: > 2
        if 0 < len(occurrences) <= 2:
            for occurrence in occurrences:
                score += langcodes_score(language, occurrence[0] + occurrence[1])
    # second test: prepended language cue in the host subdomain
    if strict and (match := HOST_LANG_FILTER.match(url)):
        score += 1 if match[1].lower() == language else -1
    return score >= 0


def path_filter(urlpath: str, query: str) -> bool:
    "Filters based on URL path: index page, imprint, etc."
    if NOTCRAWLABLE.search(urlpath):
        return False
    return bool(not INDEX_PAGE_FILTER.match(urlpath) or query)


def type_filter(url: str, strict: bool = False, with_nav: bool = False) -> bool:
    """Make sure the target URL is from a suitable type (HTML page with primarily text).
    Strict: Try to filter out other document types, spam, video and adult websites."""
    return not (
        # feeds: on the path only, query and fragment cannot hold one
        (
            ("feed" in url or "rss" in url or "_archive.html" in url)
            and FEED_FILTER.search(url.partition("?")[0].partition("#")[0])
        )
        or
        # website structure
        (SITE_STRUCTURE.search(url) and (not with_nav or not is_navigation_page(url)))
        or
        # type (also hidden in parameters), videos, adult content
        (strict and (FILE_TYPE.search(url) or ADULT_AND_VIDEOS.search(url)))
    )


def validate_url(url: str | None) -> tuple[bool, SplitResult | None]:
    "Parse and validate the input."
    if not isinstance(url, str):
        return False, None
    try:
        parsed_url = urlsplit(url)
    except ValueError:
        return False, None

    if parsed_url.scheme not in PROTOCOLS:
        return False, None

    # plausibility checks on the network location (case-insensitive for "www.")
    netloc = parsed_url.netloc
    if (
        len(netloc) < 4
        or (netloc.lower().startswith("www.") and len(netloc) < 8)
        # reject dotless/colonless hosts (e.g. "1234", "localhost")
        or ("." not in netloc and ":" not in netloc)
    ):
        return False, None

    return True, parsed_url


def is_valid_url(url: str | None) -> bool:
    "Determine if a given string is a valid URL."
    return validate_url(url)[0]


def is_navigation_page(url: str) -> bool:
    """Determine if the URL is related to navigation and overview pages
    rather than content pages, e.g. /page/1 vs. article page."""
    return bool(NAVIGATION_FILTER.search(url))


def is_not_crawlable(url: str) -> bool:
    """Run tests to check if the URL may lead to deep web or pages
    generally not usable in a crawling context."""
    return bool(NOTCRAWLABLE.search(url))
