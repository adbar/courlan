"""
Functions performing URL trimming and cleaning
"""

import logging
import re
from urllib.parse import SplitResult, parse_qs, quote, urlencode, urlunsplit

from .filters import is_valid_url
from .settings import ALLOWED_PARAMS, LANG_PARAMS, TARGET_LANGS
from .urlutils import _parse

LOGGER = logging.getLogger(__name__)

# parsing
PROTOCOLS = re.compile(r"https?://")
SELECTION = re.compile(
    r'(https?://[^">&? ]+?)(?:https?://)|(?:https?://[^/]+?/[^/]+?[&?]u(rl)?=)(https?://[^"> ]+)'
)

MIDDLE_URL = re.compile(r"https?://.+?(https?://.+?)(?:https?://|$)")
NETLOC_RE = re.compile(r"(?<=\w):(?:80|443)")

# path
PATH1 = re.compile(r"/+")
PATH2 = re.compile(r"^(?:/\.\.(?![^/]))+")

# scrub
CONTROL_CHARS = "".join(map(chr, range(0x20)))
REMAINING_MARKUP = re.compile(r"</?[a-z]{,4}?>|{.+?}")
TRAILING_AMP = re.compile(r"/\&$")
TRAILING_PARTS = re.compile(r'(.*?)[<>"\s]')

# https://github.com/AdguardTeam/AdguardFilters/blob/master/TrackParamFilter/sections/general_url.txt
# https://gitlab.com/ClearURLs/rules/-/blob/master/data.min.json
# https://firefox.settings.services.mozilla.com/v1/buckets/main/collections/query-stripping/records
TRACKERS_RE = re.compile(
    r"^(?:dc|fbc|gc|twc|yc|ysc)lid|"
    r"^(?:click|gbra|msclk|igsh|partner|wbra)id|"
    r"^(?:ads?|mc|ga|gs|itm|mc|mkt|ml|mtm|oly|pk|utm|vero)_|"
    r"(?:\b|_)(?:aff|affi|affiliate|campaign|cl?id|eid|ga|gl|"
    r"kwd|keyword|medium|ref|referr?er|session|source|uid|xtor)"
)


def clean_url(url: str, language: str | None = None) -> str | None:
    "Helper function: chained scrubbing and normalization"
    try:
        return normalize_url(scrub_url(url), False, language)
    except (AttributeError, ValueError):
        return None


def scrub_url(url: str) -> str:
    "Strip unnecessary parts and make sure only one URL is considered"
    # remove leading/trailing space and unescaped control chars
    # strip space in input string
    url = "".join(url.split()).strip(CONTROL_CHARS)

    # <![CDATA[http://...]]>
    if url.startswith("<![CDATA["):
        url = url.replace("<![CDATA[", "").replace("]]>", "")

    # markup rests
    url = REMAINING_MARKUP.sub("", url)

    # & and &amp;
    url = TRAILING_AMP.sub("", url.replace("&amp;", "&"))

    # if '"' in link:
    #    link = link.split('"')[0]

    # double/faulty URLs
    protocols = PROTOCOLS.findall(url)
    if len(protocols) > 1 and "web.archive.org" not in url:
        LOGGER.debug("double url: %s %s", len(protocols), url)
        match = SELECTION.match(url)
        if match and is_valid_url(match[1]):
            url = match[1]
            LOGGER.debug("taking url: %s", url)
        else:
            match = MIDDLE_URL.match(url)
            if match and is_valid_url(match[1]):
                url = match[1]
                LOGGER.debug("taking url: %s", url)

    # too long and garbled URLs e.g. due to quotes URLs
    match = TRAILING_PARTS.match(url)
    if match:
        url = match[1]
    if len(url) > 500:  # arbitrary choice
        LOGGER.debug("invalid-looking link %s of length %d", url[:50] + "…", len(url))

    # trailing slashes in URLs without path or in embedded URLs
    if url.count("/") == 3 or url.count("://") > 1:
        url = url.rstrip("/")

    return url


def clean_query(
    querystring: str, strict: bool = False, language: str | None = None
) -> str:
    "Strip unwanted query elements"
    if not querystring:
        return ""

    qdict = parse_qs(querystring)
    newqdict = {}

    for qelem in sorted(qdict):
        teststr = qelem.lower()
        # control param
        if strict:
            if teststr not in ALLOWED_PARAMS and teststr not in LANG_PARAMS:
                continue
        # get rid of trackers
        elif TRACKERS_RE.search(teststr):
            continue
        # control language
        if (
            language in TARGET_LANGS
            and teststr in LANG_PARAMS
            and str(qdict[qelem][0]) not in TARGET_LANGS[language]
        ):
            LOGGER.debug("bad lang: %s %s", language, qelem)
            raise ValueError
        # insert
        newqdict[qelem] = qdict[qelem]

    return urlencode(newqdict, doseq=True)


def decode_punycode(string: str) -> str:
    "Probe for punycode in lower-cased hostname and try to decode it."
    if "xn--" not in string:
        return string

    parts = []

    for part in string.split("."):
        if part.lower().startswith("xn--"):
            try:
                part = part.encode("utf8").decode("idna")
            except UnicodeError:
                LOGGER.debug("invalid utf/idna string: %s", part)
        parts.append(part)

    return ".".join(parts)


def normalize_part(url_part: str) -> str:
    """Normalize URLs parts (specifically path and fragment) while
    accounting for certain characters."""
    return quote(url_part, safe="/%!=:,-")


def normalize_fragment(fragment: str, language: str | None = None) -> str:
    "Look for trackers in URL fragments using query analysis, normalize the output."
    if "=" in fragment:
        if "&" in fragment:
            fragment = clean_query(fragment, False, language)
        elif TRACKERS_RE.search(fragment):
            fragment = ""
    return normalize_part(fragment)


def normalize_url(
    parsed_url: SplitResult | str,
    strict: bool = False,
    language: str | None = None,
    trailing_slash: bool = True,
) -> str:
    "Takes a URL string or a parsed URL and returns a normalized URL string"
    parsed_url = _parse(parsed_url)
    # lowercase + remove fragments + normalize punycode
    scheme = parsed_url.scheme.lower()
    netloc = decode_punycode(parsed_url.netloc.lower())
    # port: strip only the scheme's default port (80 for http, 443 for https)
    try:
        port = parsed_url.port
    except ValueError:
        port = None  # port could not be cast to integer value
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        netloc = NETLOC_RE.sub("", netloc)
    # path: https://github.com/saintamh/alcazar/blob/master/alcazar/utils/urls.py
    # leading /../'s in the path are removed
    newpath = normalize_part(PATH2.sub("", PATH1.sub("/", parsed_url.path)))
    # strip unwanted query elements
    newquery = clean_query(parsed_url.query, strict, language)
    if newquery and not newpath:
        newpath = "/"
    elif (
        not trailing_slash
        and not newquery
        and len(newpath) > 1
        and newpath.endswith("/")
    ):
        newpath = newpath.rstrip("/")
    # fragment
    newfragment = "" if strict else normalize_fragment(parsed_url.fragment, language)
    # rebuild
    return urlunsplit((scheme, netloc, newpath, newquery, newfragment))
