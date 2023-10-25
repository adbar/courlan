"""
URL filter and manipulation tools
https://github.com/adbar/courlan
"""

import re
import sys

from pathlib import Path
from setuptools import setup


def get_version(package):
    "Return package version as listed in `__version__` in `init.py`"
    initfile = Path(package, "__init__.py").read_text(encoding="utf-8")
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", initfile)[1]


def get_long_description():
    "Return the README"
    with open("README.rst", "r", encoding="utf-8") as filehandle:
        long_description = filehandle.read()
    # long_description += "\n\n"
    # with open("CHANGELOG.md", encoding="utf8") as f:
    #    long_description += f.read()
    return long_description


# add argument to compile with mypyc
if len(sys.argv) > 1 and sys.argv[1] == "--use-mypyc":
    sys.argv.pop(1)
    USE_MYPYC = True
    from mypyc.build import mypycify

    ext_modules = mypycify(
        [
            "courlan/__init__.py",
            "courlan/clean.py",
            "courlan/core.py",
            "courlan/filters.py",
            "courlan/langinfo.py",
            "courlan/settings.py",
            "courlan/urlstore.py",
            "courlan/urlutils.py",
        ],
        opt_level="3",
        multi_file=True,
    )
else:
    ext_modules = []


setup(
    version=get_version("courlan"),
    long_description=get_long_description(),
    url="https://github.com/adbar/courlan",
    packages=["courlan"],
    # package_data={},
    include_package_data=True,
    # extras_require=extras,
    entry_points={
        "console_scripts": ["courlan=courlan.cli:main"],
    },
    # platforms='any',
    # mypyc or not
    ext_modules=ext_modules,
)
