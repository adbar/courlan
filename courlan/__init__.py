"""
coURLan: Clean, filter, normalize, and sample URLs
"""


# meta
__title__ = 'courlan'
__author__ = 'Adrien Barbaresi'
__license__ = 'GNU GPL v3+'
__copyright__ = 'Copyright 2020, Adrien Barbaresi'
__version__ = '0.2.3'


# imports
from .clean import clean_url, normalize_url, scrub_url
from .core import check_url, extract_domain, is_external, sample_urls
from .filters import validate_url
