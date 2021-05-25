"""
Functions needed for backward compatibility.
"""


# Python 3.6+
try:
    from tld import get_fld, get_tld
    TLD_EXTRACTION, tldextract = None, None
# Python 3.5
except ImportError:
    import tldextract
    # extract callable that falls back to the included TLD snapshot, no live HTTP fetching
    TLD_EXTRACTION = tldextract.TLDExtract(suffix_list_urls=None)
    get_fld, get_tld = None, None
