"""
Unit tests for the courlan package: hosts, TLD, PSL and domain filtering.
"""

from unittest.mock import MagicMock, patch

import pytest
import urllib3

from courlan import is_external
from courlan._psl_data import EXCEPTIONS, MULTI_PART_SUFFIXES, WILDCARD_BASES
from courlan.filters import domain_filter
from courlan.hosts import (
    _idna_encode,
    _idna_label,
    _unicode_host,
    _unicode_label,
    get_registrable_domain,
)
from courlan.urlutils import get_tldinfo

_DNS_253 = "a." * 125 + "abc"  # 253 chars, at the DNS length limit
_DNS_254 = "a." * 125 + "abcd"  # 254 chars, over the limit


@pytest.mark.parametrize(
    "domain, expected",
    [
        ("", False),
        (_DNS_253, True),
        (_DNS_254, False),
        ("a" * 64 + ".org", False),
        ("a" * 63 + ".org", True),
        ("example.-com", False),
        ("example.", False),
        ("-example.com", False),
        ("_example.com", False),
        ("example.com:", False),
        ("a......b.com", False),
        ("*.example.com", False),
        ("exa-mple.co.uk", True),
        ("kräuter.de", True),
        ("xn--h1aagokeh.xn--p1ai", True),
        ("kräuter.de:8080", True),  # port split before IDNA
        ("историк.рф:8888", True),
        ("kräuter.de:99999", False),
        ("ä" * 100 + ".de", False),  # non-ASCII too long to punycode
        ("`$smarty.server.server_name`", False),
        ("$`)}if(a.tryconvertencoding)trycatch(e)const", False),
        ("00x200.jpg,", False),
        ("-100x100.webp", False),
        ("0.gravata.html", False),
        ("https:", False),
        # IPv4
        ("127.0.0.1", True),
        ("::1", True),
        ("900.200.100.75", False),
        ("111.111.111", False),
        ("0127.0.0.1", False),
        ("127.0.0.1:8080", True),
        ("900.200.100.75:8080", False),  # invalid IP, with port
        ("1.2.3.4:65535", True),
        ("1.2.3.4:99999", False),
        ("1.2.3.4:0", False),
        ("1.2.3.4:0080", False),  # leading zero rejected
        # bracketed IPv6
        ("[::1]", True),
        ("[2001:db8::1]", True),
        ("[::1]:8080", True),
        ("[::1]:0", False),
        ("[::1]:0080", False),
        ("[::1]:99999", False),
        ("[not-an-ip]", False),
        ("[::1", False),
        # trailing-dot FQDN
        ("example.com.", True),
        ("www.example.com.", True),
        ("example.com.:8080", True),
        ("192.168.0.1.", True),
        ("192.168.0.1.:8080", True),
        ("example.com..", False),  # multiple trailing dots stay invalid
        # hex-only strings that are not IPs
        ("abc.de", True),
        ("aced.de", True),
        ("dead.beef", True),
        # file extensions as top-level label
        ("example.jpg", False),
        ("example.html", False),
        ("index.html", False),
        ("site.json:8080", False),
        # real hosts: numeric first label, file type in a label, .pl and .do
        ("0.gravatar.com", True),
        ("12345.org", True),
        ("163.com", True),
        ("www.css-tricks.com", True),
        ("www.json.org", True),
        ("electron.atom.io", True),
        ("allegro.pl", True),
        ("example.do", True),
    ],
)
def test_domain_filter(domain, expected):
    "Test filters related to domain and hostnames."
    assert domain_filter(domain) is expected


@pytest.mark.parametrize(
    "host, expected",
    [
        # standard cases
        ("www.bbc.co.uk", ("bbc", "bbc.co.uk")),
        ("example.com", ("example", "example.com")),
        ("a.b.example.com", ("example", "example.com")),
        ("foo.ne.jp", ("foo", "foo.ne.jp")),
        ("shop.example.org.au", ("example", "example.org.au")),
        # IPv4 / numeric final label rejected
        ("192.168.0.1", (None, None)),
        ("www.example.42", (None, None)),
        ("example.４２", ("example", "example.４２")),  # fullwidth digits are ordinary
        # hex IPv4 rejected like decimal
        ("0xc0.0xa8.0x0.0x1", (None, None)),
        ("foo.0x1", (None, None)),
        ("foo.0XAB", (None, None)),
        ("foo.0x", (None, None)),
        ("foo.0xgg", ("foo", "foo.0xgg")),
        # IPv6 (colons) rejected
        ("2001:db8::1", (None, None)),
        ("::ffff:192.0.2.128", (None, None)),
        # trailing-dot FQDN normalized
        ("www.example.com.", ("example", "example.com")),
        # malformed / edge cases
        ("", (None, None)),
        (None, (None, None)),
        ("localhost", (None, None)),
        ("a..b.com", (None, None)),
        (".uk", (None, None)),
        (".foo.ck", (None, None)),  # leading dot + bare wildcard suffix
        # suffix-set boundary
        ("sub.unknown.xyz", ("unknown", "unknown.xyz")),
        ("blog.ax", ("blog", "blog.ax")),
        # bare public suffix
        ("co.uk", (None, None)),
        # www IS the registrable label
        ("www.co.uk", ("www", "www.co.uk")),
        ("www.gov.uk", ("www", "www.gov.uk")),
        # case-insensitive matching, original case kept
        ("BBC.CO.UK", ("BBC", "BBC.CO.UK")),
        ("Example.COM", ("Example", "Example.COM")),
        ("FOO.CK", (None, None)),
        ("X.CITY.KOBE.JP", ("CITY", "CITY.KOBE.JP")),
        ("FOO.LØDINGEN.NO", ("FOO", "FOO.LØDINGEN.NO")),
        # full-PSL coverage
        ("x.co.tz", ("x", "x.co.tz")),
        # 3-label suffix via longest-match
        ("school.act.edu.au", ("school", "school.act.edu.au")),
        # Unicode and xn-- suffix forms
        ("foo.lødingen.no", ("foo", "foo.lødingen.no")),
        ("foo.xn--ldingen-q1a.no", ("foo", "foo.xn--ldingen-q1a.no")),
        # ICANN-only: private-suffix hosts resolve as ordinary domains
        ("user.github.io", ("github", "github.io")),
        # wildcard (*.) and exception (!) PSL rules
        ("www.foo.ck", ("www", "www.foo.ck")),
        ("foo.ck", (None, None)),
        ("www.ck", ("www", "www.ck")),  # !www.ck exception
        ("a.b.kobe.jp", ("a", "a.b.kobe.jp")),
        ("x.city.kobe.jp", ("city", "city.kobe.jp")),  # !city.kobe.jp exception
        ("foo.sch.uk", (None, None)),
        ("bar.foo.sch.uk", ("bar", "bar.foo.sch.uk")),
    ],
)
def test_tld(host, expected):
    "Test get_registrable_domain."
    assert get_registrable_domain(host) == expected


def test_tld_idna_fallback():
    "Overlong non-ASCII label falls back instead of raising."
    overlong_cjk = "".join(chr(0x4E00 + i) for i in range(50))
    assert _idna_label(overlong_cjk) == overlong_cjk
    assert get_registrable_domain(f"{overlong_cjk}.example.com") == (
        "example",
        "example.com",
    )


@pytest.mark.parametrize("base", sorted(WILDCARD_BASES))
def test_tld_wildcard_bases(base):
    "Round-trip every hardcoded PSL wildcard base to catch a stale/typo'd entry."
    assert get_registrable_domain(f"x.{base}") == (None, None)
    assert get_registrable_domain(f"a.b.{base}") == ("a", f"a.b.{base}")


@pytest.mark.parametrize("exception", sorted(EXCEPTIONS))
def test_tld_exceptions(exception):
    "Round-trip every hardcoded PSL exception to catch a stale/typo'd entry."
    domain = exception.split(".")[0]
    assert get_registrable_domain(exception) == (domain, exception)
    assert get_registrable_domain(f"sub.{exception}") == (domain, exception)


def test_psl_data_encoder_consistency():
    "Generated data must be ASCII and its xn-- labels must round-trip through the runtime encoder."
    checked = 0
    for ruleset in (MULTI_PART_SUFFIXES, WILDCARD_BASES, EXCEPTIONS):
        for rule in ruleset:
            assert rule.isascii(), rule
            for label in rule.split("."):
                if label.startswith("xn--"):
                    assert _idna_encode(label.encode("ascii").decode("idna")) == label
                    checked += 1
    assert checked  # the data does contain punycode entries


def test_psl_check_ignores_header_metadata():
    "--check compares rule data, not the VERSION/COMMIT provenance header."
    from scripts.update_psl import render, strip_header_metadata

    old = render(["co.uk"], ["ck"], ["www.ck"], "v1", "aaa")
    new = render(["co.uk"], ["ck"], ["www.ck"], "v2", "bbb")
    assert old != new  # headers differ
    assert strip_header_metadata(old) == strip_header_metadata(new)  # rules identical
    changed = render(["co.uk", "gov.uk"], ["ck"], ["www.ck"], "v1", "aaa")
    assert strip_header_metadata(old) != strip_header_metadata(changed)


def test_psl_parsers():
    "PSL text parsing: header fields, ICANN-only rule extraction, rule-set split."
    from scripts.update_psl import (
        build_rule_sets,
        extract_icann_rules,
        extract_version_commit,
    )

    raw = (
        "// VERSION: 2026-07-15_00-00-00_UTC\n"
        "// COMMIT: abc123\n"
        "// ===BEGIN ICANN DOMAINS===\n"
        "// a comment\n"
        "com\n"  # single-label TLD -> dropped by build_rule_sets
        "co.uk\n"
        "\n"  # blank line
        "*.ck\n"
        "!www.ck\n"
        "  ne.jp  \n"  # whitespace stripped
        "// ===END ICANN DOMAINS===\n"
        "// ===BEGIN PRIVATE DOMAINS===\n"
        "github.io\n"  # private section -> excluded
        "// ===END PRIVATE DOMAINS===\n"
    )
    assert extract_version_commit(raw) == ("2026-07-15_00-00-00_UTC", "abc123")
    assert extract_version_commit("no headers") == ("unknown", "unknown")

    rules = extract_icann_rules(raw)
    assert rules == ["com", "co.uk", "*.ck", "!www.ck", "ne.jp"]  # ICANN only

    suffixes, wildcards, exceptions = build_rule_sets(rules)
    assert suffixes == ["co.uk", "ne.jp"]  # single-label "com" dropped
    assert wildcards == ["ck"]  # "*." stripped
    assert exceptions == ["www.ck"]  # "!" stripped

    # missing markers hard-fail (intended for a generator script)
    with pytest.raises(IndexError):
        extract_icann_rules("no markers")


@pytest.mark.parametrize(
    "kwargs",
    [
        # HTTP-status failure
        {"side_effect": RuntimeError("PSL download failed: HTTP 503")},
        # network failure (urllib3.exceptions.HTTPError, e.g. MaxRetryError)
        {"side_effect": urllib3.exceptions.MaxRetryError(None, "url")},  # type: ignore[arg-type]
        # malformed PSL text: markers missing -> IndexError from extract_icann_rules
        {"return_value": "no markers here"},
    ],
)
def test_psl_main_exit_codes(kwargs):
    "main() maps every data-error channel to exit 2, distinct from --check's exit 1."
    import scripts.update_psl as update_psl

    with patch.object(update_psl, "fetch_psl", **kwargs):
        assert update_psl.main() == 2


def test_psl_main_undecodable():
    "Undecodable payload (UnicodeDecodeError from fetch_psl) exits 2."
    import scripts.update_psl as update_psl

    with patch.object(
        urllib3.PoolManager,
        "request",
        return_value=MagicMock(status=200, data=b"\xff"),
    ):
        assert update_psl.main() == 2


@pytest.mark.parametrize(
    "url, reference, ignore_suffix, expected",
    [
        ("", "https://www.microsoft.com/", True, True),
        ("https://github.com/", "https://www.microsoft.com/", True, True),
        ("https://microsoft.com/", "https://www.microsoft.com/", True, False),
        ("https://microsoft.com/", "https://www.microsoft.com/", False, False),
        ("https://google.com/", "https://www.google.co.uk/", True, False),
        ("https://google.com/", "https://www.google.co.uk/", False, True),
        # compound suffixes: same registrable domain, different subdomains
        ("https://a.example.co.uk/", "https://b.example.co.uk/", False, False),
        # compound suffixes: different registrable domains under same ccSLD
        ("https://x.co.uk/", "https://y.co.uk/", False, True),
        # same IP in different textual forms is the same host
        ("http://[::1]/", "http://[0:0:0:0:0:0:0:1]/", True, False),
        ("http://192.168.0.1/", "http://192.168.0.1./", True, False),
        # malformed URLs
        ("h1234", "https://www.google.co.uk/", True, True),
        # stray bracket in the netloc must not raise
        ("http://sub.example.com]/x", "https://example.com/", True, True),
    ],
)
def test_external(url, reference, ignore_suffix, expected):
    """test domain comparison"""
    assert is_external(url, reference, ignore_suffix=ignore_suffix) is expected


def test_get_tldinfo_ipv6():
    "IPv6 addresses through get_tldinfo."
    # bracketed IPv6
    assert get_tldinfo("https://[2001:db8::1]/path") == ("2001:db8::1", "2001:db8::1")
    # unbracketed IPv6 (2 colons minimum)
    assert get_tldinfo("http://2001:db8::1/path") == ("2001:db8::1", "2001:db8::1")


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("xn--mnchen-3ya", "münchen"),
        # IDNA2008 deviation characters, which the stdlib idna codec rejects
        ("xn--fa-hia", "faß"),
        # invalid or non-printable decodings stay as they are
        ("xn--a", "xn--a"),
        ("xn----", "xn----"),
        ("xn--zz", "xn--zz"),
        ("example", "example"),
    ],
)
def test_unicode_label(label, expected):
    "Punycode labels decode for host comparisons."
    assert _unicode_label(label) == expected


def test_unicode_host():
    "Only the punycode labels of a host are decoded."
    assert _unicode_host("www.xn--fa-hia.de") == "www.faß.de"
    assert _unicode_host("example.org") == "example.org"
    assert not is_external("https://münchen.de/a", "https://xn--mnchen-3ya.de/")
    assert not is_external(
        "https://faß.de/a", "https://xn--fa-hia.de/", ignore_suffix=False
    )
