# URL Store — Domain-Classified URL Storage

The `UrlStore` class allows for storing and retrieving domain-classified URLs, where a URL like `https://example.org/path/page` is stored as the path `/path/page` within the domain `https://example.org`. It tracks visited and unvisited URLs per domain, supports crawl scheduling with per-domain delays, and can persist state to disk.


## Basic UrlStore usage

```{note}
`add_urls` silently drops URLs that fail validation. If URLs seem to
disappear, check them with `check_url` first to see why they are rejected.
```

```python
from courlan import UrlStore

store = UrlStore()
store.add_urls([
    'https://example.com/page1',
    'https://example.com/page2',
    'https://example.org/article',
])

# Retrieve a URL (marks it as visited with a timestamp)
url = store.get_url('https://example.com')
# 'https://example.com/page1'

# Check what's left
store.find_unvisited_urls('https://example.com')
# ['https://example.com/page2']
```


## UrlStore constructor options

| Option | Effect |
|--------|--------|
| `compressed=True` | Compress stored URLs and rules to reduce memory |
| `language='en'` | Filter added URLs by target language (ISO 639-1 code) |
| `strict=True` | Apply stricter URL filtering on add |
| `verbose=True` | Dump URLs on interrupt (requires `signal`) |

```python
store = UrlStore(language='en', strict=True, compressed=True)
```


## Tracking visited and unvisited URLs

```python
# Check if a URL is already known
store.is_known('https://example.com/page1')
# True

# Check if it has been visited
store.has_been_visited('https://example.com/page1')
# True (we called get_url above)

# Filter a list to only unknown or unvisited URLs
new_urls = ['https://example.com/page1', 'https://example.com/new']
store.filter_unknown_urls(new_urls)
# ['https://example.com/new']
store.filter_unvisited_urls(new_urls)
# ['https://example.com/new']
```


## Adding links from HTML

Extract, filter, and add links from a page in one call:

```python
html = '<a href="/page3">Link</a><a href="https://other.com/x">External</a>'
store.add_from_html(html, 'https://example.com')
# internal links added; external links ignored by default

# include external links
store.add_from_html(html, 'https://example.com', external=True)
```


## UrlStore statistics and inspection

```python
store.total_url_number()         # total URLs across all domains
store.get_known_domains()        # list of all domains
store.get_unvisited_domains()    # domains with unvisited URLs
store.unvisited_websites_number()  # count of such domains
store.get_all_counts()           # download counts per host
store.is_exhausted_domain('https://example.com')  # all URLs visited?

# Per-domain inspection
store.find_known_urls('https://example.com')
store.find_unvisited_urls('https://example.com')
store.dump_urls()                # all URLs as a flat list
```


## Discarding domains

Remove entire domains from the store:

```python
store.discard(['https://spam.example.com'])
```


## Saving and loading UrlStore state

Save and restore state across sessions. `UrlStore.write()` stores state
using Python's pickle format (see security note below). `load_store()`
restores a previously saved store.

```python
from courlan import UrlStore, load_store

store = UrlStore()
store.add_urls(['https://example.com/1', 'https://example.com/2'])
store.get_url('https://example.com')  # visit one

# Save state to disk
store.write('crawler_state.db')

# Later: resume from disk
store = load_store('crawler_state.db')
print(store.get_unvisited_domains())
```

### Persistence tips and compressed mode

- Use `compressed=True` at construction to reduce memory and on-disk
  footprint when saving large crawls: `UrlStore(compressed=True)`.
- For very large crawls, combine periodic saves with incremental files
  (e.g., `crawler_state-0001.db`, `crawler_state-0002.db`) to avoid
  single large writes and to make resuming more robust.
- If you need a human-inspectable export, use `store.dump_urls()` and
  write the flat list to a newline-delimited file.

### Common crawl workflow

A typical crawl loop using UrlStore:

```python
store = UrlStore(language='en', strict=True, compressed=True)
seed_urls = ['https://example.com']
store.add_urls(seed_urls)

while store.unvisited_websites_number() > 0:
    host = store.get_unvisited_domains()[0]
    url = store.get_url(host)
    html = fetch(url)  # your downloader
    links, nav = store.add_from_html(html, url, external=False)
    # process page and enqueue new links
    if should_checkpoint():
        store.write('crawler_state_checkpoint.db')
```

This pattern: keep frequently-accessed state in memory, persist
periodically, and prefer compressed mode for long runs.

```{warning}
`write()`/`load_store()` use Python's pickle format, which can execute
arbitrary code when loading. Only load files you have written yourself
or that you trust. Consider exporting via `dump_urls()` for sharing.
```


## Performance tips

- Use `compressed=True` for large crawls to reduce memory usage
- Save periodically with `write()` to allow resume after interruptions
- Set `language` at construction time to filter URLs on add rather than later
- Clear internal caches periodically in long-running processes: `courlan.meta.clear_caches()`


## Next steps

For crawl-specific workflows (robots.txt, crawl delays, download scheduling, frontier management), see the [Web Crawling guide](crawling.md).
