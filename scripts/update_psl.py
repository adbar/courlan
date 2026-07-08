"""
Regenerate courlan/_psl_data.py from the Mozilla Public Suffix List (PSL).

Usage:
    python scripts/update_psl.py          # fetch, regenerate, and write the file
    python scripts/update_psl.py --check  # exit 1 if the file would change

Only pull the list from the canonical URL below -- the list's own header
instructs against using any other source (e.g. VCS mirrors).
"""

import re
import sys
from pathlib import Path

import urllib3

REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
from courlan.tld import EXCEPTIONS, WILDCARD_BASES, _idna_encode  # noqa: E402

SOURCE_URL = "https://publicsuffix.org/list/public_suffix_list.dat"
OUTPUT_PATH = Path(REPO_ROOT) / "courlan" / "_psl_data.py"

HEADER = '''"""
Generated public-suffix data. Do not edit by hand -- run
scripts/update_psl.py to regenerate.
"""

# Multi-label public suffixes from the Mozilla Public Suffix List (PSL),
# ICANN section only (private-domain rules such as "github.io" excluded).
# Single-label TLDs, wildcard ("*.") and exception ("!") rules are excluded
# and handled by the implicit-* fallback / are deferred (see project notes).
# All entries are IDNA/punycode-normalized.
#
# Source: {source_url} (pull only from this URL,
# per the list's own header instructions).
# PSL VERSION: {version}
# PSL COMMIT: {commit}
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
MULTI_PART_SUFFIXES = frozenset(
    """
'''

FOOTER = '''
""".split()
)
'''


def fetch_psl() -> str:
    "Download the raw PSL text from the canonical source."
    resp = urllib3.PoolManager().request("GET", SOURCE_URL, timeout=30.0)
    return resp.data.decode("utf-8")


def extract_version_commit(raw: str) -> tuple[str, str]:
    "Pull the VERSION and COMMIT header lines out of the raw PSL text."
    version = re.search(r"^// VERSION: (.+)$", raw, re.MULTILINE)
    commit = re.search(r"^// COMMIT: (.+)$", raw, re.MULTILINE)
    return (
        version.group(1) if version else "unknown",
        commit.group(1) if commit else "unknown",
    )


def extract_icann_rules(raw: str) -> list[str]:
    "Return the raw (uncommented) rule lines within the ICANN section."
    rules, in_icann = [], False
    for line in raw.splitlines():
        if "===BEGIN ICANN DOMAINS===" in line:
            in_icann = True
        elif "===END ICANN DOMAINS===" in line:
            in_icann = False
        elif in_icann and line and not line.startswith("//"):
            rules.append(line.strip())
    return rules


def idna_normalize(rule: str) -> str | None:
    "Punycode a rule via the runtime encoder; None if a label can't be encoded."
    try:
        return ".".join(_idna_encode(label) for label in rule.split("."))
    except UnicodeError:
        return None


def build_suffix_set(rules: list[str]) -> list[str]:
    "Filter to multi-label rules, normalize, sort, dedupe; skip un-encodable ones."
    entries, skipped = set(), []
    for rule in rules:
        if rule.startswith(("*", "!")) or rule.count(".") < 1:
            continue
        normalized = idna_normalize(rule)
        if normalized is None:
            skipped.append(rule)
        else:
            entries.add(normalized)
    if skipped:
        print(f"warning: skipped {len(skipped)} un-encodable rule(s): {skipped}")
    return sorted(entries)


def check_wildcard_drift(rules: list[str]) -> None:
    "Warn if the PSL's wildcard/exception rules differ from courlan.tld's sets."
    # drop un-encodable rules (idna_normalize -> None) so sorted() stays sane
    psl_wild = {n for r in rules if r.startswith("*.") if (n := idna_normalize(r[2:]))}
    psl_exc = {n for r in rules if r.startswith("!") if (n := idna_normalize(r[1:]))}
    if psl_wild != set(WILDCARD_BASES):
        print(f"warning: WILDCARD_BASES drift -- PSL now has {sorted(psl_wild)}")
    if psl_exc != set(EXCEPTIONS):
        print(f"warning: EXCEPTIONS drift -- PSL now has {sorted(psl_exc)}")


def render(entries: list[str], version: str, commit: str) -> str:
    "Render the generated module source."
    body = "\n".join(entries)
    return (
        HEADER.format(source_url=SOURCE_URL, version=version, commit=commit)
        + body
        + FOOTER
    )


def main() -> int:
    raw = fetch_psl()
    version, commit = extract_version_commit(raw)
    icann_rules = extract_icann_rules(raw)
    check_wildcard_drift(icann_rules)
    entries = build_suffix_set(icann_rules)
    content = render(entries, version, commit)

    if "--check" in sys.argv[1:]:
        current = OUTPUT_PATH.read_text() if OUTPUT_PATH.exists() else ""
        if content != current:
            print(f"{OUTPUT_PATH} is stale ({len(entries)} entries available).")
            return 1
        print(f"{OUTPUT_PATH} is up to date ({len(entries)} entries).")
        return 0

    OUTPUT_PATH.write_text(content)
    print(f"wrote {OUTPUT_PATH} ({len(entries)} entries).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
