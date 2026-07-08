# courlan.core

Core URL checking utilities.

```{automodule} courlan.core
:members:
:undoc-members:
:show-inheritance:
```

## Common usage

```python
from courlan import check_url, extract_links, filter_links

# check_url returns (url, domain) or None if the URL is rejected
result = check_url('https://example.com/article')
if result:
    url, domain = result

# Strict mode and language filtering
result = check_url('https://example.com/article', strict=True, language='en')

# Extract links from HTML (returns a set)
links = extract_links(html, 'https://example.com', external_bool=False)

# Extract and prioritize links for crawling (returns links, priority_links)
links, priority_links = filter_links(html, 'https://example.com', lang='en')
```

## Filtering cost

Options add overhead in this order, from cheapest to most expensive:

1. **Basic** — `check_url(url)`
2. **Language filtering** — `check_url(url, language='en')` — minimal overhead
3. **Strict mode** — `check_url(url, strict=True)` — more conditions checked
4. **Redirect checks** — `check_url(url, with_redirects=True)` — network I/O; avoid on large datasets
