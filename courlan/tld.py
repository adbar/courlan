"""
Top-level domain utilities: public-suffix data and eTLD+1 extraction.
"""

from ._psl_data import MULTI_PART_SUFFIXES

# PSL wildcard (*.)/exception (!) rules, ICANN section. Stable enough to keep
# hardcoded rather than generated; scripts/update_psl.py --check warns on drift.
WILDCARD_BASES = frozenset(
    "nom.br ck er fk jm kawasaki.jp kitakyushu.jp kobe.jp nagoya.jp "
    "sapporo.jp sendai.jp yokohama.jp mm np pg sch.uk".split()
)
EXCEPTIONS = frozenset(
    "www.ck city.kawasaki.jp city.kitakyushu.jp city.kobe.jp city.nagoya.jp "
    "city.sapporo.jp city.sendai.jp city.yokohama.jp".split()
)


def _idna_encode(label: str) -> str:
    "Encode one label to ASCII/punycode; raise UnicodeError if it can't be."
    return label if label.isascii() else label.encode("idna").decode("ascii")


def _idna_label(label: str) -> str:
    "Punycode a non-ASCII label for suffix matching; pass ASCII through."
    try:
        return _idna_encode(label)
    except UnicodeError:
        return label


def get_registrable_domain(host: str | None) -> tuple[str | None, str | None]:
    "Return (domain_label, registrable_domain) from a host name."
    # host is pre-cleaned (urlsplit().hostname); a colon means IPv6, never a domain
    if not host or ":" in host or ".." in host:
        return None, None
    labels = host.strip(".").split(".")
    n = len(labels)
    if n < 2 or labels[-1].isdigit():  # reject IPv4 / numeric TLD
        return None, None
    # match punycode form, keep original form for the result (Unicode in/out)
    lookup = [_idna_label(label) for label in labels]
    psl_len = 1
    # first match wins: exception (!) -1 label, wildcard (*.) +1, else implicit last
    for i in range(n):  # range(n): a single-label wildcard base matches at i=n-1
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
