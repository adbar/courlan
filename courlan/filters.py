"""
Bundles functions needed to target text content and validate the input.
"""


## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import logging
import re

from ipaddress import ip_address
from typing import Any, Optional, Tuple
from urllib.parse import urlsplit

from langcodes import Language, tag_is_valid

from .langinfo import COUNTRY_CODES, LANGUAGE_CODES


LOGGER = logging.getLogger(__name__)


# domain/host names
IP_SET = {
    ".",
    ":",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
}

# https://github.com/python-validators/validators/blob/master/src/validators/domain.py
VALID_DOMAIN = re.compile(
    # First character of the domain
    r"^(?:[a-zA-Z0-9]"
    # Sub domain + hostname
    + r"(?:[a-zA-Z0-9-_]{0,61}[A-Za-z0-9])?\.)"
    # First 61 characters of the gTLD
    + r"+[A-Za-z0-9][A-Za-z0-9-_]{0,61}"
    # Last character of the gTLD
    + r"[A-Za-z]$",
    re.IGNORECASE,
)

UNSUITABLE_DOMAIN = re.compile(r"[0-9]+\.")

# content filters
SITE_STRUCTURE = re.compile(
    # wordpress
    r"/(?:paged?|seite|search|suche|gall?er[a-z]{1,2}|labels|archives|uploads|modules|attachment|wp-admin|wp-content|wp-includes|wp-json|wp-themes|oembed)/|"
    # wordpress + short URL
    r"[/_-](?:tags?|schlagwort|[ck]ategor[a-z]{1,2}|[ck]at|auth?or|user)/[^/]+/?$|"
    # mixed/blogspot
    r"[^0-9]/[0-9]+/[0-9]+/$|[^0-9]/[0-9]{4}/$|"
    # blogspot
    r"_archive\.html$",
    re.IGNORECASE,
)
FILE_TYPE = re.compile(
    r"\.(atom|json|css|xml|js|jpg|jpeg|png|svg|gif|tiff|pdf|ogg|mp3|m4a|aac|avi|mp4|mov|web[mp]|flv|ico|pls|zip|tar|gz|iso|swf|woff|eot|ttf)\b|"
    r"[/-](img|jpg|png)(\b|_)",
    re.IGNORECASE,
)  # (?=[&?])
ADULT_AND_VIDEOS = re.compile(
    r"[/_-](?:bild-?kontakte|fick|gangbang|incest|live-?cams?|live-?chat|porno?|sexcam|sexyeroti[ck]|swinger|x{3})\b",
    re.IGNORECASE,
)

# language filter
PATH_LANG_FILTER = re.compile(
    r"(?:https?://[^/]+/)([a-z]{2})([_-][a-z]{2,3})?(?:/)", re.IGNORECASE
)
ALL_PATH_LANGS = re.compile(r"(?:/)([a-z]{2})([_-][a-z]{2})?(?:/)", re.IGNORECASE)
HOST_LANG_FILTER = re.compile(
    r"https?://([a-z]{2})\.(?:[^.]{4,})\.(?:[^.]+)(?:\.[^.]+)?/", re.IGNORECASE
)

# navigation/crawls
NAVIGATION_FILTER = re.compile(
    r"[/_-](archives|auth?or|[ck]at|category|kategorie|paged?|schlagwort|seite|tags?|topics?|user)/|\?p=[0-9]+",
    re.IGNORECASE,
)
NOTCRAWLABLE = re.compile(
    r"/([ck]onta[ck]t|datenschutzerkl.{1,2}rung|login|impressum|imprint)(\.[a-z]{3,4})?/?$|/login\?|"
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

# territories whitelist
# see also: https://babel.pocoo.org/en/latest/api/languages.html
# get_official_languages('ch')
LANGUAGE_MAPPINGS = {
    "de": {"at", "ch", "de", "li"},  # 'be', 'it'
    "en": {"au", "ca", "en", "gb", "ie", "nz", "us"},
    "fr": {"be", "ca", "ch", "fr", "tn"},  # , 'lu', ...
}


def basic_filter(url: str) -> bool:
    """Filter URLs based on basic formal characteristics"""
    return bool(url.startswith("http") and 10 <= len(url) < 500)


def domain_filter(domain: str) -> bool:
    "Find invalid domain/host names"
    # IPv4 or IPv6
    if not set(domain).difference(IP_SET):
        try:
            ip_address(domain)
        except ValueError:
            return False
        return True

    # malformed domains
    try:
        if not VALID_DOMAIN.match(domain.encode("idna").decode("utf-8")):
            return False
    except UnicodeError:
        return False

    # unsuitable content
    if UNSUITABLE_DOMAIN.match(domain):
        return False

    if FILE_TYPE.search(domain):
        return False

    extension_match = EXTENSION_REGEX.search(domain)
    if extension_match and extension_match[0] in WHITELISTED_EXTENSIONS:
        return False

    return True


def extension_filter(urlpath: str) -> bool:
    """Filter based on file extension"""
    extension_match = EXTENSION_REGEX.search(urlpath)
    return not extension_match or extension_match[0] in WHITELISTED_EXTENSIONS


def langcodes_score(language: str, segment: str, score: int) -> int:
    """Use langcodes on selected URL segments and integrate
    them into a score."""
    # see also: https://babel.pocoo.org/en/latest/locale.html
    # test if the code looks like a country or a language
    if segment[:2] not in COUNTRY_CODES and segment[:2] not in LANGUAGE_CODES:
        return score
    # test if tag is valid (caution: private codes are)
    if tag_is_valid(segment):
        # try to identify language code
        identified = Language.get(segment).language
        # see if it matches
        if identified is not None:
            LOGGER.debug("langcode %s found in URL segment %s", identified, segment)
            if identified != language:
                score -= 1
            else:
                score += 1
    return score


def lang_filter(url: str, language: Optional[str] = None, strict: bool = False) -> bool:
    """Heuristics targeting internationalization and linguistic elements.
    Based on a score."""
    # sanity check
    if language is None:
        return True
    # init score
    score = 0
    # first test: internationalization in URL path
    match = PATH_LANG_FILTER.match(url)
    if match:
        # look for other occurrences
        occurrences = ALL_PATH_LANGS.findall(url)
        if len(occurrences) == 1:
            score = langcodes_score(language, match[1], score)
        elif len(occurrences) == 2:
            for occurrence in occurrences:
                score = langcodes_score(language, occurrence, score)
        # don't perform the test if there are too many candidates: > 2
    # second test: prepended language cues
    if strict and language in LANGUAGE_MAPPINGS:
        match = HOST_LANG_FILTER.match(url)
        if match:
            candidate = match[1].lower()
            LOGGER.debug("candidate lang %s found in URL", candidate)
            if candidate in LANGUAGE_MAPPINGS[language]:
                score += 1
            else:
                score -= 1
    # determine test result
    return score >= 0


def path_filter(urlpath: str, query: str) -> bool:
    """Filters based on URL path: index page, imprint, etc."""
    if NOTCRAWLABLE.search(urlpath):
        return False
    return bool(not INDEX_PAGE_FILTER.match(urlpath) or query)


def type_filter(url: str, strict: bool = False, with_nav: bool = False) -> bool:
    """Make sure the target URL is from a suitable type (HTML page with primarily text).
    Strict: Try to filter out other document types, spam, video and adult websites."""
    try:
        # feeds
        if url.endswith(("/feed", "/rss")):
            raise ValueError
        # website structure
        if SITE_STRUCTURE.search(url) and (not with_nav or not is_navigation_page(url)):
            raise ValueError
        # type (also hidden in parameters), videos, adult content
        if strict and (FILE_TYPE.search(url) or ADULT_AND_VIDEOS.search(url)):
            raise ValueError
    except ValueError:
        return False
    # default
    return True


def validate_url(url: Optional[str]) -> Tuple[bool, Any]:
    """Parse and validate the input"""
    try:
        parsed_url = urlsplit(url)
    except ValueError:
        return False, None
    if not bool(parsed_url.scheme) or parsed_url.scheme not in (
        "http",
        "https",
    ):
        return False, None
    # fmt: off
    if len(parsed_url.netloc) < 5 or (
        parsed_url.netloc.startswith("www.")  # type: ignore
        and len(parsed_url.netloc) < 8
    ):
        return False, None
    # fmt: on
    # default
    return True, parsed_url


def is_valid_url(url: Optional[str]) -> bool:
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
