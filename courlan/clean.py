"""
Functions performing URL trimming and cleaning
"""

import logging
import re
from urllib.parse import (
    SplitResult,
    parse_qsl,
    quote,
    quote_plus,
    unquote,
    urlunsplit,
)

from .filters import is_valid_url
from .hosts import _canonical_ip, _split_port, _unicode_host
from .settings import ALLOWED_PARAMS, LANG_PARAMS, TARGET_LANGS
from .urlutils import _parse, _strip_trailing_dot, decode_entities

LOGGER = logging.getLogger(__name__)

# parsing
PROTOCOLS = re.compile(r"https?://")
SELECTION = re.compile(r'(https?://[^">&? ]+?)(?:https?://)')

MIDDLE_URL = re.compile(r"https?://.+?(https?://.+?)(?:https?://|$)")
EMBEDDED_HOST = re.compile(r"https?://([^/?#]*)")

# netloc
DEFAULT_PORTS = {"http": 80, "https": 443}

# path
# repeated slashes, except the "//" of an embedded URL (Wayback Machine)
PATH1 = re.compile(r"(?<!:)//+")
PATH2 = re.compile(r"^(?:/\.\.(?![^/]))+")
PERCENT_ESCAPE = re.compile(r"%[0-9a-fA-F]{2}")
# written literally, so that both forms give one key
LITERAL_ESCAPES = {"%40": "@", "%2B": "+", "%3B": ";"}

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
    r"^(?:ads?|mc|ga|gs|itm|mkt|ml|mtm|oly|pk|utm|vero)_|"
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

    # before the markup and double URL steps
    url = decode_entities(url)

    # <![CDATA[http://...]]>
    if url.startswith("<![CDATA["):
        url = url.replace("<![CDATA[", "").replace("]]>", "")

    # markup rests
    url = REMAINING_MARKUP.sub("", url)

    url = TRAILING_AMP.sub("", url)

    # double/faulty URLs
    protocols = PROTOCOLS.findall(url)
    if len(protocols) > 1 and "web.archive.org" not in url:
        LOGGER.debug("double url: %s %s", len(protocols), url)
        match = SELECTION.match(url)
        if match and is_valid_url(match[1]):
            url = match[1]
        else:
            match = MIDDLE_URL.match(url)
            if match and is_valid_url(embedded := _embedded_url(match[1])):
                url = embedded

    match = TRAILING_PARTS.match(url)
    if match:
        url = match[1]
    # trailing slashes in URLs without path, embedded URLs keep theirs
    if url.count("/") == 3 and "?" not in url and "#" not in url:
        url = url.rstrip("/")

    return url


def _embedded_url(url: str) -> str:
    """Cut the outer params off an embedded URL, unless its own query
    started before them, and decode a percent-encoded host."""
    head, amp, _ = url.partition("&")
    if amp and "?" not in head:
        url = head
    if "%" in EMBEDDED_HOST.match(url)[1]:  # type: ignore[index]
        url = unquote(url)
    return url


def _encode_param(string: str) -> str:
    "Percent-encode a query element, undecodable bytes stay as they were."
    return quote_plus(string, errors="surrogateescape")


def clean_query(querystring: str, strict: bool, language: str | None = None) -> str:
    "Strip unwanted query elements"
    if not querystring:
        return ""

    qdict: dict[str, list[str]] = {}
    for segment in querystring.split("&"):
        for key, value in parse_qsl(
            segment, keep_blank_values=True, errors="surrogateescape"
        ):
            # "a" and "a=" both yield ("a", ""): keep bare keys, drop empty values
            if value or "=" not in segment:
                qdict.setdefault(key, []).append(value)

    params: list[str] = []

    for qelem in sorted(qdict):
        teststr = qelem.lower()
        # control param
        if strict:
            if teststr not in ALLOWED_PARAMS and teststr not in LANG_PARAMS:
                continue
        # get rid of trackers
        elif TRACKERS_RE.search(teststr):
            continue
        # control language, a param without value doesn't state any
        if (
            language in TARGET_LANGS
            and teststr in LANG_PARAMS
            and (lang := next(filter(None, qdict[qelem]), None))
            and lang not in TARGET_LANGS[language]
        ):
            raise ValueError("lang param")
        # insert
        key = _encode_param(qelem)
        params.extend(
            f"{key}={_encode_param(value)}" if value else key for value in qdict[qelem]
        )

    return "&".join(params)


def decode_punycode(string: str) -> str:
    "Probe for punycode in lower-cased hostname and try to decode it."
    return _unicode_host(string)


def normalize_part(url_part: str) -> str:
    """Normalize URLs parts (specifically path and fragment) while
    accounting for certain characters."""
    return quote(url_part, safe="/%!=:,-")


def normalize_fragment(fragment: str, language: str | None = None) -> str:
    "Look for trackers in URL fragments using query analysis, normalize the output."
    if "=" in fragment:
        if "&" in fragment:
            fragment = clean_query(fragment, False, language)
            # params keep their separators, as on a second pass
            if "=" in fragment:
                return quote(fragment, safe="/%!=:,-&")
        # keys only, as in clean_query
        elif TRACKERS_RE.search(fragment.partition("=")[0].lower()):
            fragment = ""
    return normalize_part(fragment)


def normalize_netloc_parts(parsed_url: SplitResult) -> tuple[str, str, str]:
    "Return the normalized (scheme, netloc, hostport), hostport without userinfo."
    userinfo, _, hostport = parsed_url.netloc.rpartition("@")
    hostport = hostport.lower()
    # split port before punycode decoding (e.g. "xn--n3h:8080"), an empty port is dropped
    host, _, port = _split_port(hostport)
    if port:
        port = str(int(port))  # ":0443" and ":443" are one port
    if host[:1] == "[" and host[-1:] == "]" and (ip := _canonical_ip(host[1:-1])):
        host = f"[{ip}]"  # one form per IPv6 address
    else:
        host = decode_punycode(_strip_trailing_dot(host))
    scheme = parsed_url.scheme.lower()
    # strip only the scheme's default port
    if port and DEFAULT_PORTS.get(scheme) == int(port):
        port = ""
    hostport = f"{host}:{port}" if port else host
    netloc = f"{userinfo}@{hostport}" if userinfo else hostport
    return scheme, netloc, hostport


def normalize_path(path: str) -> str:
    "Collapse repeated slashes, drop leading /../ segments, then percent-normalize."
    # https://github.com/saintamh/alcazar/blob/master/alcazar/utils/urls.py
    # leading /../'s in the path are removed
    path = quote(PATH2.sub("", PATH1.sub("/", path)), safe="/%!=:,-@+;")
    return PERCENT_ESCAPE.sub(_path_escape, path) if "%" in path else path


def _path_escape(match: re.Match[str]) -> str:
    escape = match[0].upper()
    return LITERAL_ESCAPES.get(escape, escape)


def rebuild_url(
    scheme: str,
    netloc: str,
    path: str,
    query: str,
    fragment: str,
    strict: bool,
    language: str | None,
    trailing_slash: bool,
) -> str:
    "Assemble the final URL string from already normalized parts."
    newfragment = "" if strict else normalize_fragment(fragment, language)
    if query and not path:
        path = "/"
    elif path == "/" and not query and not newfragment:
        # canonical root form has no trailing slash (matches scrub_url)
        path = ""
    elif not trailing_slash and not query and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, query, newfragment))


def _normalized(
    parsed_url: SplitResult,
    strict: bool,
    language: str | None,
    trailing_slash: bool,
) -> tuple[str, str, str]:
    "Return the normalized URL along with its normalized scheme and netloc."
    scheme, netloc, _ = normalize_netloc_parts(parsed_url)
    url = rebuild_url(
        scheme,
        netloc,
        normalize_path(parsed_url.path),
        clean_query(parsed_url.query, strict, language),
        parsed_url.fragment,
        strict,
        language,
        trailing_slash,
    )
    return url, scheme, netloc


def normalize_and_split(
    parsed_url: SplitResult,
    strict: bool,
    language: str | None,
    trailing_slash: bool,
) -> tuple[str, str, str]:
    "Return the normalized (url, base, path) triple from a single set of parts."
    url, scheme, netloc = _normalized(parsed_url, strict, language, trailing_slash)
    # without a netloc urlunsplit drops the "//" and the slice below would cut
    # into the path instead of past the host
    if not netloc:
        raise ValueError(f"no host to split off: {url}")
    # the store key leaves out the userinfo
    path = url[len(f"{scheme}://{netloc}") :] or "/"
    return url, f"{scheme}://{netloc.rpartition('@')[2]}", path


def normalize_url(
    parsed_url: SplitResult | str,
    strict: bool = False,
    language: str | None = None,
    trailing_slash: bool = True,
) -> str:
    "Takes a URL string or a parsed URL and returns a normalized URL string."
    return _normalized(_parse(parsed_url), strict, language, trailing_slash)[0]
