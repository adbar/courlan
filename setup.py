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
    name="courlan",
    version=get_version("courlan"),
    description="Clean, filter and sample URLs to optimize data collection – includes spam, content type and language filters.",
    long_description=get_long_description(),
    classifiers=[
        # As from http://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 4 - Beta",
        #'Development Status :: 5 - Production/Stable',
        #'Development Status :: 6 - Mature',
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Text Processing :: Filters",
        "Topic :: Text Processing :: Linguistic",
    ],
    keywords=[
        "cleaner",
        "crawler",
        "preprocessing",
        "url-parsing",
        "url-manipulation",
        "urls",
        "validation",
        "webcrawling",
    ],
    url="https://github.com/adbar/courlan",
    author="Adrien Barbaresi",
    author_email="barbaresi@bbaw.de",
    license="Apache-2.0",
    packages=["courlan"],
    project_urls={
        "Blog": "https://adrien.barbaresi.eu/blog/",  # /tag/courlan.html
        "Tracker": "https://github.com/adbar/courlan/issues",
    },
    # package_data={},
    include_package_data=True,
    python_requires=">=3.6",
    install_requires=[
        "langcodes >= 3.3.0",
        "tld == 0.12.6; python_version < '3.7'",
        "tld >= 0.13; python_version >= '3.7'",
        "urllib3 >= 1.26, < 2; python_version < '3.7'",
        "urllib3 >= 1.26, < 3; python_version >= '3.7'",
    ],
    # extras_require=extras,
    entry_points={
        "console_scripts": ["courlan=courlan.cli:main"],
    },
    # platforms='any',
    tests_require=["pytest"],
    zip_safe=False,
    # mypyc or not
    ext_modules=ext_modules,
)
