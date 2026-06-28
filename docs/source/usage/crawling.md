# Web Crawling with Courlan

Guide to building web crawlers with courlan: frontier management, crawl delays, link extraction, and persistence.

## UrlStore for Crawler State

The `UrlStore` class manages the crawl frontier: tracking visited/unvisited URLs per domain and handling robots.txt rules.

### Basic Crawler Loop

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
        # store.add_urls(extract_links(response.text, url))
```

### Key UrlStore Methods

| Method | Purpose |
|--------|---------|
| `add_urls(urls)` | Add URLs to frontier |
| `get_url(domain)` | Retrieve next URL and mark as visited |
| `get_unvisited_domains()` | Domains with unvisited URLs |
| `unvisited_websites_number()` | Count of domains with remaining URLs |
| `establish_download_schedule(max_urls, time_limit)` | Batch URLs with per-domain delays |
| `download_threshold_reached(threshold)` | Check if time limit exceeded |
| `find_unvisited_urls(domain)` | List unvisited URLs for a domain |
| `is_exhausted_domain(domain)` | Check if domain has no more URLs |
| `write(filename)` | Save state to disk |

---

## Crawl Delays

Use `get_crawl_delay()` to read the delay from stored robots.txt rules, and `store_rules()` / `get_rules()` to persist them.

```python
from courlan import UrlStore
from urllib.robotparser import RobotFileParser
import time

store = UrlStore()
domain = 'https://example.com'

# Store robots.txt rules after fetching
rules = RobotFileParser(f'{domain}/robots.txt')
rules.read()
store.store_rules(domain, rules)

# Apply delay between requests
delay = store.get_crawl_delay(domain, default=5)
time.sleep(delay)
url = store.get_url(domain)
```

### Scheduled Download Strategy

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

for delay, url in schedule:
    time.sleep(delay)
    print(f"Fetching: {url}")
    # response = requests.get(url)
    if store.download_threshold_reached(threshold=60):
        break
```

---

## Crawler Frontier Management

### Scope Detection

```python
from courlan import is_external

if not is_external(found_url, 'https://example.com', ignore_suffix=False):
    store.add_urls([found_url])
```

### Navigation Page Detection

```python
from courlan import is_navigation_page

for url in candidate_urls:
    if not is_navigation_page(url):
        store.add_urls([url])  # content page, high priority
```

### Crawlability Detection

```python
from courlan import is_not_crawlable

for url in candidate_urls:
    if not is_not_crawlable(url):
        store.add_urls([url])
```

---

## Extracting Links from HTML

```python
from courlan import extract_links

links = extract_links(
    html,
    base_url,
    external_bool=False,
    language='en',
    strict=True,
)
store.add_urls(links)
```

`extract_links` also accepts `no_filter`, `redirects`, and `with_nav` — see the API reference for details.

---

## Persistence and Resume

```python
from courlan import UrlStore, load_store

store = UrlStore()
store.add_urls(['https://example.com/page1', 'https://example.com/page2'])
store.get_url('https://example.com')

store.write('crawler_state.db')

# Later session:
store = load_store('crawler_state.db')
print(f"Unvisited domains: {store.get_unvisited_domains()}")
```

---

## Best Practices

| Practice | Reason |
|----------|--------|
| Respect robots.txt | Legal/ethical requirement |
| Set crawl delays | Avoid overloading servers |
| Identify User-Agent | Tell servers who you are |
| Save crawler state | Resume after interruptions |
| Skip navigation pages | Focus on content |
| Validate URLs | Avoid malformed requests |
| Handle errors gracefully | Don't crash on bad pages |
| Limit crawl scope | Stay on target domain(s) |

---

## Complete Example

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

---

## Troubleshooting

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
