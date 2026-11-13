"""
Functions related to URL manipulation and extraction of URL parts.
"""

import re
from collections.abc import Collection
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

from .hosts import (
    _ascii_host,
    _canonical_ip,
    _compared_host,
    _split_port,
    get_registrable_domain,
)

_NUMERIC_AMP = re.compile(r"&#0*38;|&#x0*26;", re.I)
FEED_WHITELIST_REGEX = re.compile(r"(?:feed(?:burner|proxy))", re.I)


def _strip_trailing_dot(host: str) -> str:
    "Drop a single trailing FQDN dot from host or host:port; multiple dots stay invalid."
    if host.endswith(".") and not host.endswith(".."):
        return host[:-1]
    head, sep, tail = host.rpartition(":")
    if sep and "@" not in host and head.endswith(".") and not head.endswith(".."):
        return f"{head[:-1]}:{tail}"
    return host


def get_tldinfo(url: str) -> tuple[str | None, str | None]:
    "Extract domain info via the public-suffix lookup, returning a ``(domain, full_domain)`` tuple."
    if not isinstance(url, str) or not url:
        return None, None
    parsed = _parse(url)  # never raises: malformed netlocs degrade to empty parts
    host = parsed.hostname
    if host:
        host = _strip_trailing_dot(host)  # FQDN form would defeat the IP gate below
    # IP literals are returned in canonical form; gates avoid the exception
    # cost of ip_address() on the common non-IP case
    if host and (":" in host or host[-1].isdigit()) and (ip := _canonical_ip(host)):
        return ip, ip
    # unbracketed IPv6 isn't in .hostname; retry on the netloc (userinfo stripped)
    if parsed.netloc.count(":") >= 2:
        netloc_host = _strip_trailing_dot(parsed.netloc.rsplit("@", 1)[-1])
        if netloc_host.count(":") >= 2 and (ip := _canonical_ip(netloc_host)):
            return ip, ip
    return get_registrable_domain(host)


def extract_domain(
    url: str, blacklist: set[str] | None = None, fast: bool = False
) -> str | None:
    """Extract domain name information using top-level domain info.
    ``fast`` is accepted for backward compatibility but no longer has any effect."""
    domain, full_domain = get_tldinfo(url)
    if not full_domain or (
        blacklist and (domain in blacklist or full_domain in blacklist)
    ):
        return None
    return full_domain


def _parse(url: str | SplitResult) -> SplitResult:
    "Parse a string or use urllib.parse object directly."
    if isinstance(url, str):
        try:
            # "&amp;" and numeric ampersand entities only: full unescape()
            # also expands query keys that happen to be entity names,
            # turning "&param=" into "\xb6m="
            parsed_url = urlsplit(_NUMERIC_AMP.sub("&", url.replace("&amp;", "&")))
        except ValueError:
            # malformed URL (e.g. bad IPv6 literal): degrade to empty parts like a hostless URL.
            parsed_url = SplitResult("", "", "", "", "")
    elif isinstance(url, SplitResult):
        parsed_url = url
    else:
        raise TypeError("wrong input type:", type(url))
    return parsed_url


def get_base_url(url: str | SplitResult) -> str:
    """Strip URL of some of its parts to get base URL.
    Accepts strings and urllib.parse ParseResult objects."""
    parsed_url = _parse(url)
    if parsed_url.scheme:
        return f"{parsed_url.scheme}://{parsed_url.netloc}"
    return parsed_url.netloc


def get_ascii_url(url: str) -> str:
    """Return the URL with its host in punycode, the form HTTP clients can fetch.
    Other URL parts are left as they are."""
    try:
        netloc = urlsplit(url).netloc
    except ValueError:
        return url
    userinfo, sep, hostport = netloc.rpartition("@")
    host, colon, port = _split_port(hostport)
    return url.replace(netloc, f"{userinfo}{sep}{_ascii_host(host)}{colon}{port}", 1)


def get_host_and_path(url: str | SplitResult) -> tuple[str, str]:
    """Decompose URL in two parts: protocol + host/domain and path.
    Accepts strings and urllib.parse ParseResult objects."""
    parsed_url = _parse(url)
    hostname = get_base_url(parsed_url)
    if not hostname:
        raise ValueError(f"incomplete URL: {url}")
    # "/" for the root/homepage
    path = urlunsplit(("", "", parsed_url.path, parsed_url.query, parsed_url.fragment))
    return hostname, path or "/"


def get_hostinfo(url: str) -> tuple[str | None, str]:
    "Convenience function returning domain and host info (protocol + host/domain) from a URL."
    return extract_domain(url), get_base_url(url)


def fix_relative_urls(baseurl: str, url: str) -> str:
    """Prepend protocol and host information to relative links.

    Raises:
        ValueError: if the base URL or the link is malformed.
    """
    if url.startswith("{"):
        return url

    # malformed URLs raise ValueError, callers rely on it to drop them
    parsed_base = urlsplit(baseurl)
    split_url = urlsplit(url)

    if split_url.netloc not in (parsed_base.netloc, ""):
        if split_url.scheme:
            return url
        return urlunsplit(split_url._replace(scheme=parsed_base.scheme or "http"))

    return urljoin(baseurl, url)


def filter_urls(link_list: list[str], urlfilter: str | None) -> list[str]:
    "Return a list of links corresponding to the given substring pattern."
    if urlfilter is not None:
        # feedburner option: filter and wildcards for feeds
        link_list = [link for link in link_list if urlfilter in link] or [
            link for link in link_list if FEED_WHITELIST_REGEX.search(link)
        ]
    return sorted(set(link_list))


def is_external(url: str, reference: str, ignore_suffix: bool = True) -> bool:
    """Determine if a link leads to another host, takes a reference URL and
    a URL as input, returns a boolean"""
    # domain label or full domain, compared in unicode form as check_url decodes punycode
    i = 0 if ignore_suffix else 1
    return _compared_host(get_tldinfo(url)[i]) != _compared_host(
        get_tldinfo(reference)[i]
    )


def _swap_scheme(url: str) -> str:
    "Switch between http and https in a URL or scheme-prefixed domain."
    return "http" + url[5:] if url.startswith("https") else "https" + url[4:]


def _slash_variant(url: str) -> str:
    "Add a trailing slash, or drop the trailing ones if there are any."
    return url.rstrip("/") if url[-1] == "/" else url + "/"


def is_known_link(link: str, known_links: Collection[str]) -> bool:
    "Compare the link and its possible variants to the existing URL base."
    if not link:
        return False
    # exact link and trailing slash variant
    if link in known_links or _slash_variant(link) in known_links:
        return True
    if not link.startswith("http"):
        return False
    # the same with the other protocol
    swapped = _swap_scheme(link)
    return swapped in known_links or _slash_variant(swapped) in known_links
