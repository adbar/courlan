"""Run the Python examples of the README and the usage docs and check the
outputs shown in `# <literal>` comments."""

import ast
import doctest
import re
import socket
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
PAGES = [
    ROOT / "README.md",
    ROOT / "docs/source/getting-started.md",
    *sorted((ROOT / "docs/source/usage").glob("*.md")),
]
# a MyST comment line before the fence skips a block (placeholders, network)
BLOCK = re.compile(r"^(% skip-example\n)?``` ?python\n(.*?)^```", re.M | re.S)


def _offline(*_: Any) -> None:
    raise AssertionError("docs example needs the network, mark it % skip-example")


def _blocks(text: str) -> list[str]:
    return [m.group(2) for m in BLOCK.finditer(text) if not m.group(1)]


def _expected(lines: list[str], stmt: ast.stmt) -> tuple[bool, Any]:
    "Find the literal shown inline or on the comment lines right after."
    assert stmt.end_lineno is not None
    candidates = []
    _, _, inline = lines[stmt.end_lineno - 1].partition("  # ")
    if inline:
        candidates.append(inline)
    comment = ""
    for line in lines[stmt.end_lineno :]:
        if not line.startswith("#"):
            break
        comment += line[1:].strip()
        candidates.append(comment)
    for text in candidates:
        try:
            return True, ast.literal_eval(text.strip())
        except (ValueError, SyntaxError):
            continue
    return False, None


def _run(source: str, namespace: dict[str, Any]) -> None:
    if ">>>" in source:
        test = doctest.DocTestParser().get_doctest(source, namespace, "", None, 0)
        runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
        assert runner.run(test, clear_globs=False).failed == 0
        return
    lines = source.splitlines()
    for stmt in ast.parse(source).body:
        found, expected = _expected(lines, stmt)
        if isinstance(stmt, ast.Expr) and found:
            code = compile(ast.Expression(stmt.value), "<docs>", "eval")
            assert eval(code, namespace) == expected, ast.unparse(stmt)
            continue
        exec(compile(ast.Module([stmt], []), "<docs>", "exec"), namespace)
        if found and isinstance(stmt, ast.Assign):
            target = stmt.targets[0]
            assert isinstance(target, ast.Name), ast.unparse(stmt)
            assert namespace[target.id] == expected, ast.unparse(stmt)


@pytest.mark.parametrize("page", PAGES, ids=[p.name for p in PAGES])
def test_docs_examples(
    page: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(socket.socket, "connect", _offline)
    namespace: dict[str, Any] = {}
    for source in _blocks(page.read_text("utf-8")):
        _run(source, namespace)


def test_skip_marker() -> None:
    page = "% skip-example\n```python\nfetch()\n```\n```python\nx = 1\n```\n"
    assert _blocks(page) == ["x = 1\n"]
