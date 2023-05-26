"""
Functions performing URL trimming and cleaning
"""

## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import logging
import re

from typing import Optional, Union
from urllib.parse import parse_qs, urlencode, urlunsplit, ParseResult

from .filters import validate_url
from .settings import ALLOWED_PARAMS, CONTROL_PARAMS, TARGET_LANG_DE, TARGET_LANG_EN
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
REMAINING_MARKUP = re.compile(r"</?[a-z]{,4}?>|{.+?}")
TRAILING_AMP = re.compile(r"/\&$")
TRAILING_PARTS = re.compile(r'(.*?)[<>"\'\s]')


def clean_url(url: str, language: Optional[str] = None) -> Optional[str]:
    """Helper function: chained scrubbing and normalization"""
    try:
        return normalize_url(scrub_url(url), False, language)
    except (AttributeError, ValueError):
        return None


def scrub_url(url: str) -> str:
    """Strip unnecessary parts and make sure only one URL is considered"""
    # trim
    # https://github.com/cocrawler/cocrawler/blob/main/cocrawler/urls.py
    # remove leading and trailing white space and unescaped control chars
    url = url.strip(
        "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
        "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f \r\n"
    )
    # clean the input string
    url = url.replace("[ \t]+", "")
    # <![CDATA[http://www.urbanlife.de/item/260-bmw-i8-hybrid-revolution-unter-den-sportwagen.html]]>
    if url.startswith("<![CDATA["):
        url = url.replace("<![CDATA[", "")  # url = re.sub(r'^<!\[CDATA\[', '', url)
        url = url.replace("]]>", "")  # url = re.sub(r'\]\]>$', '', url)
    # markup rests
    url = REMAINING_MARKUP.sub("", url)
    # & and &amp;
    if "&amp;" in url:
        url = url.replace("&amp;", "&")
    url = TRAILING_AMP.sub("", url)
    # if '"' in link:
    #    link = link.split('"')[0]
    # double/faulty URLs
    protocols = PROTOCOLS.findall(url)
    if len(protocols) > 1 and "web.archive.org" not in url:
        LOGGER.debug("double url: %s %s", len(protocols), url)
        match = SELECTION.match(url)
        if match and validate_url(match[1])[0] is True:
            url = match[1]
            LOGGER.debug("taking url: %s", url)
        else:
            match = MIDDLE_URL.match(url)
            if match and validate_url(match[1])[0] is True:
                url = match[1]
                LOGGER.debug("taking url: %s", url)
    # too long and garbled URLs e.g. due to quotes URLs
    # https://github.com/cocrawler/cocrawler/blob/main/cocrawler/urls.py
    # if len(url) > 500:  # arbitrary choice
    match = TRAILING_PARTS.match(url)
    if match:
        url = match[1]
    if len(url) > 500:
        LOGGER.debug("invalid-looking link %s of length %d", url[:50] + "…", len(url))

    # trailing slashes in URLs without path or in embedded URLs
    if url.count("/") == 3 or url.count("://") > 1:
        url = url.rstrip("/")
    # lower
    # url = url.lower()
    return url


def clean_query(
    parsed_url: ParseResult, strict: bool = False, language: Optional[str] = None
) -> str:
    """Strip unwanted query elements"""
    if len(parsed_url.query) > 0:
        qdict = parse_qs(parsed_url.query)
        newqdict = {}
        for qelem in sorted(qdict):
            teststr = qelem.lower()
            # control param
            if (
                strict
                and teststr not in ALLOWED_PARAMS
                and teststr not in CONTROL_PARAMS
            ):
                continue
            # control language
            if language is not None and teststr in CONTROL_PARAMS:
                found_lang = str(qdict[qelem][0])
                if (
                    (language == "de" and found_lang not in TARGET_LANG_DE)
                    or (language == "en" and found_lang not in TARGET_LANG_EN)
                    or found_lang != language
                ):
                    LOGGER.info("bad lang: %s %s %s", language, qelem, found_lang)
                    raise ValueError
            # insert
            newqdict[qelem] = qdict[qelem]
        return urlencode(newqdict, doseq=True)
    return parsed_url.query


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


def normalize_url(
    parsed_url: Union[ParseResult, str],
    strict: bool = False,
    language: Optional[str] = None,
) -> str:
    """Takes a URL string or a parsed URL and returns a (basically) normalized URL string"""
    parsed_url = _parse(parsed_url)
    # lowercase + remove fragments + normalize punycode
    scheme = parsed_url.scheme.lower()
    # port
    if parsed_url.port and parsed_url.port in (80, 443):
        netloc = NETLOC_RE.sub("", parsed_url.netloc)
    else:
        netloc = parsed_url.netloc
    # lowercase + remove fragments + normalize punycode
    netloc = decode_punycode(netloc.lower())
    # path: https://github.com/saintamh/alcazar/blob/master/alcazar/utils/urls.py
    # leading /../'s in the path are removed
    newpath = PATH2.sub("", PATH1.sub("/", parsed_url.path))
    # strip unwanted query elements
    newquery = clean_query(parsed_url, strict, language) or ""
    if newquery and newpath == "":
        newpath = "/"
    # fragment
    newfragment = "" if strict else parsed_url.fragment
    # rebuild
    return urlunsplit([scheme, netloc, newpath, newquery, newfragment])
