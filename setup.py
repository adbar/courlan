"""
URL filter and manipulation tools
https://github.com/adbar/courlan
"""

import sys

from setuptools import setup


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
            "courlan/sampling.py",
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
    # mypyc or not
    ext_modules=ext_modules,
)
