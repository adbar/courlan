"""
Meta-functions to be applied module-wide.
"""

import logging

from .filters import langcodes_score

LOGGER = logging.getLogger(__name__)

try:
    from urllib.parse import clear_cache as urllib_clear_cache  # type: ignore
except ImportError:  # pragma: no cover

    def urllib_clear_cache() -> None:
        "Fallback when urllib.parse.clear_cache is unavailable."
        LOGGER.warning("urllib.parse.clear_cache is unavailable, skipping")


def clear_caches() -> None:
    """Reset all known LRU caches used to speed up processing.
    This may release some memory."""
    urllib_clear_cache()
    langcodes_score.cache_clear()
