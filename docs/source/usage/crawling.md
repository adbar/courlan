---
myst:
  html_meta:
    description: "Build web crawlers with courlan: crawl delays, robots.txt, download scheduling, frontier management."
---

# Web Crawling with Courlan

Guide to building web crawlers with courlan: crawl delays, robots.txt, download scheduling, frontier management, and link extraction.

This guide assumes familiarity with `UrlStore` basics — see the [URL Store guide](urlstore.md) first.


## Basic crawler loop

```python
from courlan import UrlStore

store = UrlStore(language='en', strict=True)
store.add_urls([
    'https://example.com/page1',
    'https://example.com/page2',
    'https://other.org/article',
])

while store.unvisited_websites_number() > 0:
    for domain in store.get_unvisited_domains():
        url = store.get_url(domain)  # marks as visited
        if not url:
            continue
        print(f"Visiting: {url}")
        # response = requests.get(url, timeout=10)
        # store.add_from_html(response.text, url)
```


## Crawl delays and robots.txt

Use `store_rules()` / `get_rules()` to persist robots.txt rules, and `get_crawl_delay()` to read the delay.

```python
from courlan import UrlStore
from urllib.robotparser import RobotFileParser
import time

store = UrlStore()
domain = 'https://example.com'

# Fetch and store robots.txt rules (requires network access)
rules = RobotFileParser(f'{domain}/robots.txt')
rules.read()
store.store_rules(domain, rules)

# Apply delay between requests
delay = store.get_crawl_delay(domain, default=5)
time.sleep(delay)
url = store.get_url(domain)
```


## Scheduled downloads

For large crawls, `establish_download_schedule()` batches URLs with appropriate per-domain delays:

```python
from courlan import UrlStore
import time

store = UrlStore()
store.add_urls([
    'https://a.com/1', 'https://a.com/2',
    'https://b.org/x', 'https://b.org/y',
])

schedule = store.establish_download_schedule(max_urls=100, time_limit=10)

# or get a flat list of immediately-downloadable URLs (no delays)
ready = store.get_download_urls(max_urls=50, time_limit=10)

for delay, url in schedule:
    time.sleep(delay)
    print(f"Fetching: {url}")
    # response = requests.get(url)
    if store.download_threshold_reached(threshold=60):
        break
```


## Frontier management

### Scope detection

```python
from courlan import is_external

if not is_external(found_url, 'https://example.com', ignore_suffix=False):
    store.add_urls([found_url])
```

### Crawlability detection

```python
from courlan import is_not_crawlable, is_navigation_page

for url in candidate_urls:
    if is_not_crawlable(url):
        continue  # skip login pages, deep web, etc.
    if is_navigation_page(url):
        continue  # skip listing/index pages
    store.add_urls([url])
```

```{note}
`filter_links` already separates navigation pages into a priority list
(via `with_nav=True` by default). The manual check above is useful when
you process URLs outside of `filter_links`.
```


## Extracting links from HTML

```python
from courlan import extract_links

links = extract_links(
    html,
    url,
    external_bool=False,
    language='en',
    # strict=True is the default for extract_links
)
store.add_urls(links)
```

`extract_links` also accepts `no_filter`, `trailing_slash`, `with_nav`, `redirects`, `reference`, and `base_url` — see the [API reference](../api/core.md) for details.


## Best practices

| Practice | Reason |
|----------|--------|
| Respect robots.txt | Legal/ethical requirement |
| Set crawl delays | Avoid overloading servers |
| Identify User-Agent | Tell servers who you are |
| Save crawler state | Resume after interruptions |
| Separate navigation pages | Crawl them for link discovery, deprioritize for content extraction |
| Validate URLs | Avoid malformed requests |
| Handle errors gracefully | Don't crash on bad pages |
| Limit crawl scope | Stay on target domain(s) |


## Complete example

```python
from courlan import UrlStore, extract_links, is_not_crawlable
import time

store = UrlStore(language='en', strict=True)
store.add_urls(['https://example.com'])
pages_crawled = 0

while store.unvisited_websites_number() > 0 and pages_crawled < 100:
    for domain in store.get_unvisited_domains():
        url = store.get_url(domain)
        if not url or is_not_crawlable(url):
            continue
        try:
            # response = requests.get(url, timeout=10)
            # links = extract_links(response.text, url, external_bool=False)
            # store.add_urls(links)
            pages_crawled += 1
            time.sleep(2)
        except Exception as e:
            print(f"Error: {url} - {e}")

store.write('crawler_state.db')
```


## Troubleshooting crawls

**URL not added to store** — `UrlStore.add_urls()` silently drops invalid URLs. Validate first:

```python
from courlan import check_url

if check_url(url, strict=True) is None:
    print("URL failed validation")
```

**Memory growing during a long crawl** — use `compressed=True` and periodically clear caches:

```python
from courlan import UrlStore
from courlan.meta import clear_caches

store = UrlStore(compressed=True)
# ... process URLs ...
clear_caches()
```
