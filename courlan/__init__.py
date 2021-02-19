"""
coURLan: Clean, filter, normalize, and sample URLs
"""


# meta
__title__ = 'courlan'
__author__ = 'Adrien Barbaresi'
__license__ = 'GNU GPL v3+'
__copyright__ = 'Copyright 2020-2021, Adrien Barbaresi'
__version__ = '0.3.1'


# imports
from .clean import clean_url, normalize_url, scrub_url
from .core import check_url, extract_domain, extract_links, is_external, sample_urls
from .filters import lang_filter, validate_url
