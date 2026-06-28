import shutil
import subprocess
from pathlib import Path

import pytest

DOCS_SOURCE = Path(__file__).parent / "source"
DOCS_BUILD = Path(__file__).parent / "_build"
DOCS_HTML = DOCS_BUILD / "html"


@pytest.fixture(autouse=True, scope="module")
def clean_build():
    if DOCS_BUILD.exists():
        shutil.rmtree(DOCS_BUILD)
    yield


def test_sphinx_build_succeeds():
    cmd = ["sphinx-build", "-W", "-b", "html", str(DOCS_SOURCE), str(DOCS_HTML)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        pytest.fail(
            f"Sphinx build failed (exit {result.returncode})\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    assert (DOCS_HTML / "index.html").exists()
