"""
Regression tests: valueless and blank-valued query parameters must
survive URL cleaning.

Stock courlan 1.4.0 drops them silently because ``clean_query`` calls
``parse_qs`` without ``keep_blank_values=True``. Dropping parameters is
courlan's documented job only for trackers (TRACKERS_RE) and, in strict
mode, for names outside the allowlist; a parameter's *value* being
empty is not a removal criterion.
"""

from urllib.parse import parse_qsl, unquote, urlsplit

from courlan import check_url, clean_url
from courlan.clean import normalize_url


def param_names(url):
    return [k for k, _ in parse_qsl(urlsplit(url).query, keep_blank_values=True)]


def fragment_param_names(url):
    # unquote first: how the cleaned fragment *encodes* its separators is
    # a separate behaviour (see ASSESSMENT.md, finding S2); this test only
    # asserts which parameters survive cleaning.
    fragment = unquote(urlsplit(url).fragment)
    return [k for k, _ in parse_qsl(fragment, keep_blank_values=True)]


def test_valueless_param_preserved():
    "A bare flag parameter (?amp) selects a page variant; it must survive."
    assert "amp" in param_names(clean_url("https://example.com/page?amp"))


def test_blank_value_param_preserved():
    "An explicitly empty value (?a=) is not the same as an absent parameter."
    cleaned = clean_url("https://example.com/page?a=&b=2")
    assert param_names(cleaned) == ["a", "b"]


def test_mixed_valueless_and_valued_params():
    cleaned = clean_url("https://example.com/page?download&x=1")
    assert param_names(cleaned) == ["download", "x"]


def test_check_url_preserves_blank_params():
    checked = check_url("https://example.com/page?flag&flag2=&id=7")
    assert checked is not None
    assert param_names(checked[0]) == ["flag", "flag2", "id"]


def test_tracker_with_blank_value_still_dropped():
    "The tracker filter works on names; a blank value must not exempt it."
    cleaned = clean_url("https://example.com/p?utm_source=&id=3")
    assert param_names(cleaned) == ["id"]


def test_strict_mode_allowlist_still_applies():
    "Strict mode drops by name as before; allowlisted blank params survive."
    cleaned = normalize_url("https://example.com/p?id=&amp", strict=True)
    assert param_names(cleaned) == ["id"]


def test_fragment_query_blank_param_preserved():
    "Fragments cleaned as queries follow the same rule."
    cleaned = clean_url("https://example.com/app#a=&view=grid")
    assert fragment_param_names(cleaned) == ["a", "view"]
