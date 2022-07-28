"""
coURLan: Clean, filter, normalize, and sample URLs
"""


# meta
__title__ = "courlan"
__author__ = "Adrien Barbaresi"
__license__ = "GNU GPL v3+"
__copyright__ = "Copyright 2020-2022, Adrien Barbaresi"
__version__ = "0.8.3"


# imports
from .clean import clean_url, normalize_url, scrub_url
from .core import check_url, extract_links, sample_urls
from .filters import is_navigation_page, is_not_crawlable, lang_filter, validate_url
from .urlstore import UrlStore
from .urlutils import (
    extract_domain,
    filter_urls,
    fix_relative_urls,
    get_base_url,
    get_host_and_path,
    get_hostinfo,
    is_external,
)
