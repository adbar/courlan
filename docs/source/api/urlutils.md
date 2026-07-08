# courlan.urlutils

URL parsing, decomposition, and relative URL resolution utilities.

```{automodule} courlan.urlutils
:members:
:undoc-members:
:show-inheritance:
```

## Common usage

```python
from courlan import extract_domain, get_base_url, get_host_and_path, fix_relative_urls
from courlan import get_hostinfo, filter_urls

# Extract domain from URL
domain = extract_domain('https://www.example.com/path', fast=True)

# Get base URL (scheme + netloc)
base = get_base_url('https://example.com/path/page?q=1')

# Decompose URL into host and path
host, path = get_host_and_path('https://example.com/articles/post')

# Convenience: domain name + base URL in one call
domainname, base_url = get_hostinfo('https://www.example.com/path')

# Resolve relative URLs
absolute = fix_relative_urls('https://example.com', 'articles/post.html')

# Filter a list of URLs by substring pattern (None = deduplicate only)
subset = filter_urls(link_list, urlfilter='example.com')
```
