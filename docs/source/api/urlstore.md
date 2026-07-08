# courlan.urlstore

Domain-classified URL storage for web crawling workflows.

```{automodule} courlan.urlstore
:members:
:undoc-members:
:show-inheritance:
```

For crawler-oriented usage (crawl loops, scheduling, robots.txt, HTML link extraction), see the [Web Crawling guide](../usage/crawling.md).

## Examples

### Basic URL tracking

```python
from courlan import UrlStore

store = UrlStore()
store.add_urls([
    'https://example.com/page1',
    'https://example.com/page2',
    'https://example.org/article',
])

while store.unvisited_websites_number() > 0:
    for domain in store.get_unvisited_domains():
        url = store.get_url(domain)  # marks URL as visited
        if url:
            print(f"Processing: {url}")
            store.add_urls(['https://example.com/page3'])
```

### Persistent store (save/load)

```python
from courlan import UrlStore, load_store

# Build store over time
store = UrlStore()
store.add_urls(['https://example.com/1', 'https://example.com/2'])
store.get_url('https://example.com')  # mark as visited

# Save to disk
store.write('my_urls.db')

# Later: load from disk (different session)
store = load_store('my_urls.db')

# Continue where you left off
print(f"Total URLs: {store.total_url_number()}")
print(f"Unvisited domains: {store.get_unvisited_domains()}")
```

### Statistics and reporting

```python
from courlan import UrlStore

store = UrlStore()
store.add_urls([
    'https://a.com/1', 'https://a.com/2', 'https://a.com/3',
    'https://b.org/x', 'https://b.org/y',
    'https://c.net/article',
])

# Mark some as visited
store.get_url('https://a.com')
store.get_url('https://a.com')

# Generate statistics
print(f"Total URLs: {store.total_url_number()}")
print(f"Known domains: {store.get_known_domains()}")
print(f"Unvisited domains: {store.get_unvisited_domains()}")

# Per-domain stats
for domain in store.get_known_domains():
    all_urls = store.find_known_urls(domain)
    unvisited = store.find_unvisited_urls(domain)
    print(f"{domain}: {len(all_urls)} total, {len(unvisited)} unvisited")
```

### Filtering and deduplication

```python
from courlan import UrlStore

store = UrlStore()
store.add_urls(['https://example.com/page', 'https://example.org/post'])

# Check if URL is already known
if store.is_known('https://example.com/page'):
    print("Already in store")

# Filter unknown URLs
new_urls = ['https://example.com/page', 'https://example.com/new']
unknown = store.filter_unknown_urls(new_urls)
print(f"Unknown URLs: {unknown}")

# Filter unvisited URLs
unvisited = store.filter_unvisited_urls(new_urls)
```

## Performance tips

- **For large crawls**: Use `compressed=True` to reduce memory
- **Storage**: Save the store periodically with `write(filename)`
- **Scheduling**: Use `establish_download_schedule()` to respect crawl delays
- **Languages**: Set language filter at init to filter links automatically: `UrlStore(language='en')`

