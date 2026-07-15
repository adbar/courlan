"""
Functions related to URL manipulation and extraction of URL parts.
"""

import re
from html import unescape
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

from .hosts import _canonical_ip, get_registrable_domain

FEED_WHITELIST_REGEX = re.compile(r"(?:feed(?:burner|proxy))", re.I)


def _strip_trailing_dot(host: str) -> str:
    "Drop a single trailing dot (FQDN form); multiple trailing dots stay invalid."
    return host[:-1] if host.endswith(".") and not host.endswith("..") else host


def get_tldinfo(url: str, fast: bool = False) -> tuple[str | None, str | None]:
    """Extract domain info, returning a ``(domain, full_domain)`` tuple.
    ``fast`` is accepted for backward compatibility but no longer changes the
    result: extraction always goes through the public-suffix lookup."""
    if not url or not isinstance(url, str):
        return None, None
    try:
        parsed = _parse(url)
        host = parsed.hostname
    except ValueError:  # e.g. unbalanced brackets in the netloc
        return None, None
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
    if blacklist is None:
        blacklist = set()
    domain, full_domain = get_tldinfo(url)

    return (
        full_domain
        if full_domain and domain not in blacklist and full_domain not in blacklist
        else None
    )


def _parse(url: str | SplitResult) -> SplitResult:
    "Parse a string or use urllib.parse object directly."
    if isinstance(url, str):
        parsed_url = urlsplit(unescape(url))
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
        scheme = parsed_url.scheme + "://"
    else:
        scheme = ""
    return scheme + parsed_url.netloc


def get_host_and_path(url: str | SplitResult) -> tuple[str, str]:
    """Decompose URL in two parts: protocol + host/domain and path.
    Accepts strings and urllib.parse ParseResult objects."""
    parsed_url = _parse(url)
    hostname = get_base_url(parsed_url)
    pathval = urlunsplit(
        ["", "", parsed_url.path, parsed_url.query, parsed_url.fragment]
    )
    # correction for root/homepage
    if pathval == "":
        pathval = "/"
    if not hostname or not pathval:
        raise ValueError(f"incomplete URL: {url}")
    return hostname, pathval


def get_hostinfo(url: str) -> tuple[str | None, str]:
    "Convenience function returning domain and host info (protocol + host/domain) from a URL."
    domainname = extract_domain(url)
    base_url = get_base_url(url)
    return domainname, base_url


def fix_relative_urls(baseurl: str, url: str) -> str:
    "Prepend protocol and host information to relative links."
    if url.startswith("{"):
        return url

    parsed_base = urlsplit(baseurl)
    base_netloc = parsed_base.netloc
    split_url = urlsplit(url)

    if split_url.netloc not in (base_netloc, ""):
        if split_url.scheme:
            return url
        return urlunsplit(split_url._replace(scheme=parsed_base.scheme or "http"))

    return urljoin(baseurl, url)


def filter_urls(link_list: list[str], urlfilter: str | None) -> list[str]:
    "Return a list of links corresponding to the given substring pattern."
    if urlfilter is None:
        return sorted(set(link_list))
    # filter links
    filtered_list = [link for link in link_list if urlfilter in link]
    # feedburner option: filter and wildcards for feeds
    if not filtered_list:
        filtered_list = [
            link for link in link_list if FEED_WHITELIST_REGEX.search(link)
        ]
    return sorted(set(filtered_list))


def is_external(url: str, reference: str, ignore_suffix: bool = True) -> bool:
    """Determine if a link leads to another host, takes a reference URL and
    a URL as input, returns a boolean"""
    stripped_ref, ref = get_tldinfo(reference)
    stripped_domain, domain = get_tldinfo(url)
    # comparison
    if ignore_suffix:
        return stripped_domain != stripped_ref
    return domain != ref


def is_known_link(link: str, known_links: set[str]) -> bool:
    "Compare the link and its possible variants to the existing URL base."
    if not link:
        return False
    # check exact link
    if link in known_links:
        return True

    # check link and variants with trailing slashes
    slash_test = link.rstrip("/") if link[-1] == "/" else link + "/"
    if slash_test in known_links:
        return True

    # check link and variants with modified protocol
    if link.startswith("http"):
        protocol_test = (
            "http" + link[5:] if link.startswith("https") else "https" + link[4:]
        )
        slash_test = (
            protocol_test.rstrip("/")
            if protocol_test[-1] == "/"
            else protocol_test + "/"
        )
        if protocol_test in known_links or slash_test in known_links:
            return True

    return False
