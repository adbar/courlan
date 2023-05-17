"""
Meta-functions to be applied module-wide.
"""

from urllib.parse import clear_cache as urllib_clear_cache  # type: ignore[attr-defined]

from .urlutils import get_tldinfo


def clear_caches() -> None:
    """Reset all known LRU caches used to speed up processing.
    This may release some memory."""
    urllib_clear_cache()
    get_tldinfo.cache_clear()
