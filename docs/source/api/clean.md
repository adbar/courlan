# courlan.clean

Core URL cleaning and normalization utilities.

```{automodule} courlan.clean
:members:
:undoc-members:
:show-inheritance:
```

## Common usage

```python
from courlan import clean_url, scrub_url, normalize_url, validate_url

# Clean and normalize a URL (returns str or None if invalid)
url = clean_url('HTTPS://WWW.EXAMPLE.COM:443/path?utm_source=x')

# Basic validation
is_valid, parsed = validate_url('https://example.com')

# Normalization only
normalized = normalize_url('http://example.com/path?z=1&a=2#fragment')
```
