"""Build the documentation with Sphinx to catch broken pages or references.
Run in CI for the Python version used on Read the Docs."""

import posixpath
import subprocess
from pathlib import Path

import pytest
from sphinx.util.inventory import InventoryFile

DOCS_SOURCE = Path(__file__).parent / "source"


@pytest.fixture(scope="module")
def build(tmp_path_factory):
    """Build once, with warnings treated as errors."""
    target = tmp_path_factory.mktemp("html")
    result = subprocess.run(
        ["sphinx-build", "-W", "-b", "html", str(DOCS_SOURCE), str(target)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Sphinx build failed (exit {result.returncode})\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return target


def test_sphinx_build_succeeds(build):
    assert (build / "index.html").exists()


def test_api_reference_is_generated(build):
    """MyST renders an automodule directive outside eval-rst as plain text
    instead of API documentation, without emitting a warning."""
    with open(build / "objects.inv", "rb") as filehandle:
        inventory = InventoryFile.load(filehandle, "", posixpath.join)
    assert "courlan.core.check_url" in inventory.get("py:function", {}), sorted(
        inventory
    )
