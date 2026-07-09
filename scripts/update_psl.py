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

from courlan.network import RETRY_STRATEGY

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_URL = "https://publicsuffix.org/list/public_suffix_list.dat"
OUTPUT_PATH = REPO_ROOT / "courlan" / "_psl_data.py"
# refuse to write if the fetched list shrinks implausibly
# (~5,470 suffixes, 16 wildcard and 8 exception rules as of 2026)
MIN_SUFFIXES, MIN_WILDCARDS, MIN_EXCEPTIONS = 5000, 10, 5

TEMPLATE = '''"""
Generated public-suffix data. Do not edit by hand -- run
scripts/update_psl.py to regenerate.
"""

# Rules from the Mozilla Public Suffix List (PSL), ICANN section only
# (private-domain rules such as "github.io" excluded). Single-label TLDs
# are excluded and handled by the implicit-* fallback. All entries are
# IDNA/punycode-normalized.
#
# Source: {source_url} (pull only from this URL,
# per the list's own header instructions).
# PSL VERSION: {version}
# PSL COMMIT: {commit}
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Multi-label public suffixes.
MULTI_PART_SUFFIXES = frozenset(
    """
{suffixes}
""".split()
)

# Wildcard ("*.") rule bases: every direct child label is a public suffix.
WILDCARD_BASES = frozenset(
    """
{wildcards}
""".split()
)

# Exception ("!") rules: hosts exempted from a wildcard rule above.
EXCEPTIONS = frozenset(
    """
{exceptions}
""".split()
)
'''


def fetch_psl() -> str:
    "Download the raw PSL text from the canonical source."
    pool = urllib3.PoolManager(retries=RETRY_STRATEGY)
    resp = pool.request("GET", SOURCE_URL, timeout=30.0)
    if resp.status != 200:
        raise RuntimeError(f"PSL download failed: HTTP {resp.status}")
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
    "Punycode a rule; None if a label can't be encoded (mirrors courlan.tld._idna_label)."
    try:
        return ".".join(
            label if label.isascii() else label.encode("idna").decode("ascii")
            for label in rule.split(".")
        )
    except UnicodeError:
        return None


def build_rule_sets(rules: list[str]) -> tuple[list[str], list[str], list[str]]:
    "Split rules into (suffixes, wildcard bases, exceptions), normalized and sorted."
    suffixes: set[str] = set()
    wildcards: set[str] = set()
    exceptions: set[str] = set()
    skipped = []
    for rule in rules:
        if rule.startswith("*."):
            target, rule = wildcards, rule[2:]
        elif rule.startswith("!"):
            target, rule = exceptions, rule[1:]
        elif rule.count(".") < 1:  # single-label TLDs: implicit-* fallback
            continue
        else:
            target = suffixes
        normalized = idna_normalize(rule)
        if normalized is None:
            skipped.append(rule)
        else:
            target.add(normalized)
    if skipped:
        print(f"warning: skipped {len(skipped)} un-encodable rule(s): {skipped}")
    return sorted(suffixes), sorted(wildcards), sorted(exceptions)


def render(
    suffixes: list[str],
    wildcards: list[str],
    exceptions: list[str],
    version: str,
    commit: str,
) -> str:
    "Render the generated module source."
    return TEMPLATE.format(
        source_url=SOURCE_URL,
        version=version,
        commit=commit,
        suffixes="\n".join(suffixes),
        wildcards="\n".join(wildcards),
        exceptions="\n".join(exceptions),
    )


def main() -> int:
    raw = fetch_psl()
    version, commit = extract_version_commit(raw)
    suffixes, wildcards, exceptions = build_rule_sets(extract_icann_rules(raw))
    counts = f"{len(suffixes)}/{len(wildcards)}/{len(exceptions)} rules"
    if (
        len(suffixes) < MIN_SUFFIXES
        or len(wildcards) < MIN_WILDCARDS
        or len(exceptions) < MIN_EXCEPTIONS
    ):
        print(f"error: implausibly small rule set ({counts}), refusing to continue.")
        return 1
    content = render(suffixes, wildcards, exceptions, version, commit)

    if "--check" in sys.argv[1:]:
        current = OUTPUT_PATH.read_text() if OUTPUT_PATH.exists() else ""
        if content != current:
            print(f"{OUTPUT_PATH} is stale ({counts} available).")
            return 1
        print(f"{OUTPUT_PATH} is up to date ({counts}).")
        return 0

    OUTPUT_PATH.write_text(content)
    print(f"wrote {OUTPUT_PATH} ({counts}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
