"""
Top-level domain utilities: public-suffix data and eTLD+1 extraction.
"""

import re

from ._psl_data import MULTI_PART_SUFFIXES

STRIP_PORT_REGEX = re.compile(r"(?<=\D):\d+")


def get_registrable_domain(netloc: str) -> tuple[str | None, str | None]:
    "Return (domain_label, registrable_domain) from a netloc string."
    auth_stripped = netloc.split("@")[-1]
    if auth_stripped.startswith("["):  # IPv6 literal, never a registrable domain
        return None, None
    host = STRIP_PORT_REGEX.sub("", auth_stripped).rstrip(".").lower()
    if not host or ".." in host:
        return None, None
    labels = host.split(".")
    if len(labels) < 2 or labels[-1].isdigit():  # reject IPv4 / numeric TLD
        return None, None
    # try the longest candidate suffix first; unmatched hosts fall back to
    # treating the last label as the (unvalidated) suffix
    suffix_len = 1
    for i in range(len(labels) - 1):
        if ".".join(labels[i:]) in MULTI_PART_SUFFIXES:
            suffix_len = len(labels) - i
            break
    if suffix_len >= len(labels):  # host is itself a bare public suffix
        return None, None
    domain_start = -(suffix_len + 1)
    return labels[domain_start], ".".join(labels[domain_start:])
