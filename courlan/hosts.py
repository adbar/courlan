"""
Host utilities shared by urlutils and filters: IP-literal canonicalization,
punycode encoding and decoding, public-suffix data and eTLD+1 extraction.
"""

import ipaddress
import re
from functools import lru_cache

from ._psl_data import EXCEPTIONS, MULTI_PART_SUFFIXES, WILDCARD_BASES

# longest rule across all sets bounds how many label-suffixes can ever match
_MAX_RULE_LABELS = 1 + max(
    rule.count(".")
    for rules in (MULTI_PART_SUFFIXES, WILDCARD_BASES, EXCEPTIONS)
    for rule in rules
)


def _canonical_ip(candidate: str) -> str | None:
    "Return the canonical form of an IP literal, or None if it isn't one."
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _split_port(hostport: str) -> tuple[str, str, str]:
    """Split a trailing decimal port off as (host, ":", port).
    No port or a malformed netloc ("x:80:80") gives (hostport, "", "")."""
    host, sep, port = hostport.rpartition(":")
    if (
        not sep
        or (":" in host and not host.endswith("]"))
        or (port and not (port.isascii() and port.isdecimal()))
    ):
        return hostport, "", ""
    return host, sep, port


def _ascii_label(label: str) -> str:
    "Punycode a non-ASCII label, IDNA2008 deviations included."
    if label.isascii():
        return label
    return "xn--" + label.encode("punycode").decode("ascii")


def _unicode_label(label: str) -> str:
    """Decode a punycode label, IDNA2008 deviations included.
    Keep it if invalid or if the stdlib codec cannot encode it again."""
    if not label.startswith("xn--"):
        return label
    try:
        decoded = label[4:].encode("ascii").decode("punycode")
        decoded.encode("idna")  # domain_filter's validator, rejects e.g. RTL + digit
    except UnicodeError:
        return label
    # the raw codec does not validate: "xn--a" gives "\x80", "xn----" gives "-",
    # "xn--wca" gives "Ü", whose lowercased host re-encodes to another label
    # an ASCII result never re-encodes to an xn-- label
    if decoded.isprintable() and _ascii_label(decoded.lower()) == label:
        return decoded
    return label


def _unicode_host(host: str) -> str:
    "Decode the punycode labels of a lowercased host, for host comparisons."
    if "xn--" not in host:
        return host
    return ".".join(_unicode_label(label) for label in host.split("."))


def _compared_host(host: str | None) -> str | None:
    "Return the unicode form of a possibly missing host, for host comparisons."
    return host and _unicode_host(host)


def _ascii_host(host: str) -> str:
    "Punycode the non-ASCII labels of a host."
    if host.isascii():
        return host
    return ".".join(_ascii_label(label) for label in host.lower().split("."))


# IPv4 candidate per WHATWG: ASCII decimal/octal digits, or 0x/0X plus hex digits
_NUMERIC_LABEL = re.compile(r"[0-9]+|0[xX][0-9a-fA-F]*")


@lru_cache(maxsize=1024)
def get_registrable_domain(host: str | None) -> tuple[str | None, str | None]:
    "Return (domain_label, registrable_domain) from a host name."
    # host is pre-cleaned (urlsplit().hostname); a colon means IPv6, never a domain
    if not host or ":" in host or ".." in host:
        return None, None
    labels = host.strip(".").split(".")
    n = len(labels)
    if n < 2 or _NUMERIC_LABEL.fullmatch(
        labels[-1]
    ):  # reject IPv4 (incl. hex) / numeric TLD
        return None, None
    # match lowercase punycode form, keep original form for the result
    lookup = (
        labels
        if host.isascii() and host.islower()
        else [_ascii_label(label.lower()) for label in labels]
    )
    psl_len = 1
    # first match wins: exception (!) -1 label, wildcard (*.) +1, else implicit last
    # suffixes longer than the longest rule can't match; single-label wildcard
    # bases still match at i=n-1
    for i in range(max(0, n - _MAX_RULE_LABELS), n):
        cand = ".".join(lookup[i:])
        if cand in EXCEPTIONS:
            psl_len = n - i - 1
            break
        if cand in MULTI_PART_SUFFIXES:
            psl_len = n - i
            break
        if i and cand in WILDCARD_BASES:
            psl_len = n - i + 1
            break
    if psl_len >= n:  # a host that is itself a public suffix is its own domain
        domain = ".".join(labels)
        return domain, domain
    start = -(psl_len + 1)
    return labels[start], ".".join(labels[start:])
