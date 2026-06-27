"""
Top-level domain utilities: curated compound-suffix list and eTLD+1 extraction.
"""

import re

STRIP_PORT_REGEX = re.compile(r"(?<=\D):\d+")

# Curated subset of the Mozilla PSL ICANN section: two-label compound suffixes
# for ~44 high-traffic ccTLDs. Every entry has been validated against the PSL.
# fmt: off
MULTI_PART_SUFFIXES = frozenset({
    "ac.ae", "ac.at", "ac.be", "ac.cn", "ac.eg", "ac.id", "ac.il", "ac.in",
    "ac.jp", "ac.ke", "ac.kr", "ac.nz", "ac.pk", "ac.se", "ac.th", "ac.uk",
    "ac.vn", "ac.za",
    "co.ae", "co.at", "co.id", "co.il", "co.in", "co.it", "co.jp", "co.ke",
    "co.kr", "co.nz", "co.th", "co.uk", "co.za",
    "com.ar", "com.au", "com.br", "com.cn", "com.eg", "com.es", "com.fr",
    "com.gr", "com.hk", "com.in", "com.mx", "com.my", "com.ng", "com.ph",
    "com.pk", "com.pl", "com.pt", "com.sa", "com.sg", "com.tr", "com.tw",
    "com.ua", "com.vn",
    "edu.ar", "edu.au", "edu.br", "edu.cn", "edu.eg", "edu.es", "edu.gr",
    "edu.hk", "edu.in", "edu.it", "edu.mx", "edu.my", "edu.ng", "edu.ph",
    "edu.pk", "edu.pl", "edu.pt", "edu.sa", "edu.sg", "edu.tr", "edu.tw",
    "edu.ua", "edu.vn", "edu.za",
    "gen.in", "gen.nz", "gen.tr",
    "go.id", "go.it", "go.jp", "go.ke", "go.kr", "go.th",
    "gob.ar", "gob.es", "gob.mx", "gob.pk",
    "gouv.fr",
    "gov.ae", "gov.ar", "gov.au", "gov.br", "gov.cn", "gov.eg", "gov.gr",
    "gov.hk", "gov.il", "gov.in", "gov.it", "gov.my", "gov.ng", "gov.ph",
    "gov.pk", "gov.pl", "gov.pt", "gov.sa", "gov.sg", "gov.tr", "gov.tw",
    "gov.ua", "gov.uk", "gov.vn", "gov.za",
    "govt.nz",
    "mil.ae", "mil.ar", "mil.br", "mil.cn", "mil.eg", "mil.id", "mil.in",
    "mil.kr", "mil.my", "mil.ng", "mil.no", "mil.nz", "mil.ph", "mil.pl",
    "mil.tr", "mil.tw", "mil.za",
    "ne.jp", "ne.ke", "ne.kr",
    "net.ae", "net.ar", "net.au", "net.br", "net.cn", "net.eg", "net.gr",
    "net.hk", "net.id", "net.il", "net.in", "net.mx", "net.my", "net.ng",
    "net.nz", "net.ph", "net.pk", "net.pl", "net.pt", "net.sa", "net.sg",
    "net.th", "net.tr", "net.tw", "net.ua", "net.uk", "net.vn", "net.za",
    "nic.in", "nic.za",
    "or.at", "or.id", "or.it", "or.jp", "or.ke", "or.kr", "or.th",
    "org.ae", "org.ar", "org.au", "org.br", "org.cn", "org.eg", "org.es",
    "org.gr", "org.hk", "org.il", "org.in", "org.mx", "org.my", "org.ng",
    "org.nz", "org.ph", "org.pk", "org.pl", "org.pt", "org.sa", "org.se",
    "org.sg", "org.tr", "org.tw", "org.ua", "org.uk", "org.vn", "org.za",
    "res.in",
    "sch.ae", "sch.id", "sch.ng", "sch.sa",
})
# fmt: on


def get_registrable_domain(netloc: str) -> tuple[str | None, str | None]:
    "Return (domain_label, registrable_domain) from a netloc string."
    host = STRIP_PORT_REGEX.sub("", netloc.split("@")[-1]).rstrip(".").lower()
    if not host or ".." in host:
        return None, None
    labels = host.split(".")
    if len(labels) < 2 or labels[-1].isdigit():  # reject IPv4 / numeric TLD
        return None, None
    # registrable domain spans the last 3 labels for a known compound suffix,
    # else the last 2
    span = 3 if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_PART_SUFFIXES else 2
    return labels[-span], ".".join(labels[-span:])
