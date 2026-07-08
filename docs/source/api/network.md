# courlan.network

Network helpers for redirect checking and HTTP operations.

```{automodule} courlan.network
:members:
:undoc-members:
:show-inheritance:
```

## Common usage

```python
# Redirect checking is typically used through check_url() function
from courlan import check_url

# Check if URL redirects (makes HTTP HEAD request)
url, domain = check_url('https://example.com/old-page', with_redirects=True)
```
