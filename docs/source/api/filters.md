# courlan.filters

URL filtering heuristics for content validation and crawler optimization.

```{automodule} courlan.filters
:members:
:undoc-members:
:show-inheritance:
```

## Common usage

```python
from courlan import check_url, filter_links, lang_filter, is_valid_url

# check_url returns (url, domain) or None if rejected
result = check_url('https://example.com/article', language='en', strict=True)
if result:
    url, domain = result

# Extract and filter links from HTML
html = '<a href="/page1">Link</a><a href="/tag/spam">Tag</a>'
links, priority_links = filter_links(html, 'https://example.com', lang='en')

# Test if a URL matches a target language heuristically
if lang_filter('https://example.com/en/article', language='en'):
    print("Language matches")

# Basic structural validity check (no network call)
if is_valid_url('https://example.com/path'):
    print("Valid URL structure")
```
