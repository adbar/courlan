"""
Host utilities shared by urlutils and filters: IP-literal canonicalization,
IDNA/punycode encoding, public-suffix data and eTLD+1 extraction.
"""

import ipaddress
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


def _idna_encode(label: str) -> str:
    "Encode a label or dotted name to ASCII/punycode; raise UnicodeError if it can't be."
    return label if label.isascii() else label.encode("idna").decode("ascii")


def _idna_label(label: str) -> str:
    "Punycode a non-ASCII label for suffix matching; pass ASCII through."
    try:
        return _idna_encode(label)
    except UnicodeError:
        return label


_HEX_DIGITS = frozenset("0123456789abcdef")


def _is_numeric_label(label: str) -> bool:
    "IPv4 candidate per WHATWG: decimal/octal digits, or 0x/0X plus hex digits."
    # ASCII-only (WHATWG): rejects fullwidth/other non-ASCII digits
    if label.isascii() and label.isdigit():
        return True
    if label[:2].lower() != "0x":
        return False
    return all(c in _HEX_DIGITS for c in label[2:].lower())


@lru_cache(maxsize=1024)
def get_registrable_domain(host: str | None) -> tuple[str | None, str | None]:
    "Return (domain_label, registrable_domain) from a host name."
    # host is pre-cleaned (urlsplit().hostname); a colon means IPv6, never a domain
    if not host or ":" in host or ".." in host:
        return None, None
    labels = host.strip(".").split(".")
    n = len(labels)
    if n < 2 or _is_numeric_label(labels[-1]):  # reject IPv4 (incl. hex) / numeric TLD
        return None, None
    # match lowercase punycode form, keep original form for the result
    lookup = (
        labels
        if host.isascii() and host.islower()
        else [_idna_label(label.lower()) for label in labels]
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
    if psl_len >= n:  # host is itself a public suffix
        return None, None
    start = -(psl_len + 1)
    return labels[start], ".".join(labels[start:])
