# courlan.meta

Cache management and meta-utilities.

```{automodule} courlan.meta
:members:
:undoc-members:
:show-inheritance:
```

## Cache Management

Courlan uses LRU (Least Recently Used) caches to speed up URL parsing and language detection. For long-running processes, you can clear these caches to reclaim memory.

### clear_caches()

**Purpose**: Reset all internal LRU caches.

Use in long-running processes handling many distinct URLs, in memory-constrained environments, or between crawl phases.

**What gets cleared**: urllib.parse results, language detection scores.

**Example**:
```python
from courlan import check_url
from courlan.meta import clear_caches

for i in range(10000):
    result = check_url(f'https://example.com/page{i}')
    if (i + 1) % 1000 == 0:
        clear_caches()
```

---

## Usage in Batch Workflows

```python
from courlan import UrlStore, check_url
from courlan.meta import clear_caches

store = UrlStore(compressed=True)
store.add_urls(many_urls)

# Process in batches
batch_size = 5000
processed = 0

while store.unvisited_websites_number() > 0:
    for domain in store.get_unvisited_domains():
        url = store.get_url(domain)
        if url:
            check_url(url, strict=True, language='en')
            processed += 1
            
            # Clear caches periodically
            if processed % batch_size == 0:
                clear_caches()
                print(f"Processed {processed} URLs, caches cleared")
```

---

## See Also

- [Web Crawling guide](../usage/crawling.md) — cache clearing in crawler workflows
