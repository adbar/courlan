---
myst:
  html_meta:
    description: "How to validate, clean, normalize, and filter URLs in Python with courlan."
---

# URL Checking, Cleaning, and Filtering in Python

Most filters revolve around the `strict` and `language` arguments. This page covers URL checking, cleaning, normalization, link extraction, and sampling.


## Checking URLs with check_url

`check_url` is the main entry point — it validates, normalizes, and filters a URL in one call. Returns `(url, domain)` on success or `None` if rejected.

```{note}
`check_url` returns `None` for rejected URLs — always check the return value before unpacking.
```

```python
from courlan import check_url

result = check_url('https://example.com/article?utm_source=twitter')
if result:
    url, domain = result
    # url = 'https://example.com/article', domain = 'example.com'
```

### Language filtering

Pass a two-letter ISO 639-1 code to keep only URLs that match the target language (detected from path segments, subdomains, and query parameters):

```python
# accepted: English path segment
check_url('https://www.un.org/en/about-us', language='en')
# ('https://www.un.org/en/about-us', 'un.org')

# rejected: English URL but German requested
check_url('https://www.un.org/en/about-us', language='de')
# None
```

For standalone language detection without the full check_url pipeline, use `lang_filter`:

```python
from courlan import lang_filter

if lang_filter('https://example.com/en/article', language='en'):
    print("Language matches")
```

### Strict mode

`strict=True` enables more aggressive filtering — blacklisted domains, adult content, and suspicious paths are rejected, query parameters are trimmed more aggressively, and language detection uses subdomains too.

:::{dropdown} Full comparison: default vs strict
:icon: table

| Area | Default | With `strict=True` |
|------|---------|-------------------|
| **Query parameters** | Only known trackers removed | All parameters removed except a small allowlist (`page`, `id`, `post`, etc.) |
| **URL fragments** | Normalized | Stripped entirely |
| **File extensions** | Non-web extensions rejected (`.jpg`, `.pdf`, `.zip`, etc.) | Same, plus pattern-based detection (e.g. `/img/`, `?file=doc.pdf`) |
| **Adult/video content** | Not checked | URLs with adult or video path patterns rejected |
| **Domain blacklist** | Not applied | URLs from the platforms listed in `BLACKLIST` rejected (social media, CDNs, e-commerce, etc.) |
| **Path filtering** | Not applied | Index/landing pages without a query string (`index`, `home`, `default`), plus contact/login/imprint paths, are rejected |
| **Language detection** | Path-based only | Subdomain-based language signals also considered |
:::

```python
# blocked in strict mode: major platform in the blacklist
check_url('https://www.twitter.com/', strict=True)
# None

# query parameters trimmed more aggressively
check_url('https://httpbin.org/redirect-to?url=http%3A%2F%2Fexample.org', strict=True)
# ('https://httpbin.org/redirect-to', 'httpbin.org')

# adult content pattern rejected in strict mode
check_url('https://example.com/porn/page', strict=True)
# None
```

The blacklist and allowlists can be customized at runtime — see the [settings reference](../api/settings.md).

### Other options

| Option | Effect |
|--------|--------|
| `with_redirects=True` | Follow HTTP redirects (HEAD request — slow) |
| `with_nav=True` | Accept navigation/listing pages instead of discarding them |
| `trailing_slash=False` | Strip trailing slashes |

### Filtering cost

Options add overhead in this order, from cheapest to most expensive:

1. **Basic** — `check_url(url)`
2. **Language filtering** — `check_url(url, language='en')` — minimal overhead
3. **Strict mode** — `check_url(url, strict=True)` — more conditions checked
4. **Redirect checks** — `check_url(url, with_redirects=True)` — network I/O; avoid on large datasets

All options compose freely, e.g. `check_url(url, language='en', strict=True)`.


## Cleaning and normalizing URLs

```{warning}
`clean_url` normalizes but does **not** validate. It can return `None`
on malformed input but will happily return a munged string for
structurally valid garbage. Use `check_url` or `validate_url` if you
need to reject invalid URLs.
```

For cleaning without the full filtering pipeline:

```python
from courlan import clean_url

# Lowercase scheme/host, strip default port, remove trackers
clean_url('HTTPS://WWW.DWDS.DE:443/')
# 'https://www.dwds.de'
```

`clean_url` also takes `language` (ISO 639-1), which discards URLs whose
`lang`/`language` query parameter contradicts the target language.

For low-level scrubbing only (strip markup residues, control characters, and tracking artifacts without normalizing):

```python
from courlan import scrub_url

scrub_url('<![CDATA[http://example.com]]>')
# 'http://example.com'
```

For canonicalization only (reorder query params, strip fragments):

```python
from courlan import normalize_url

normalize_url('http://test.net/foo.html?utm_source=twitter&post=abc&page=2#fragment', strict=True)
# 'http://test.net/foo.html?page=2&post=abc'
```

For structural validation without normalization:

```python
from courlan import validate_url

validate_url('http://1234')
# (False, None)

validate_url('http://www.example.org/')
# (True, SplitResult(...))
```

For a simple boolean check (wrapper around `validate_url`):

```python
from courlan import is_valid_url

is_valid_url('http://www.example.org/')
# True
```


## URL parsing and decomposition utilities

Decompose and manipulate URLs with `extract_domain`, `get_base_url`, `get_host_and_path`, `get_hostinfo`, and `fix_relative_urls`:

```python
from courlan import extract_domain, get_base_url, get_host_and_path, get_hostinfo, fix_relative_urls

url = 'https://www.un.org/en/about-us'

extract_domain(url)             # 'un.org'

get_base_url(url)               # 'https://www.un.org'
get_host_and_path(url)          # ('https://www.un.org', '/en/about-us')
get_hostinfo(url)               # ('un.org', 'https://www.un.org')

fix_relative_urls('https://www.un.org', 'en/about-us')
# 'https://www.un.org/en/about-us'
```

Filter and deduplicate URL lists:

```python
from courlan import filter_urls

subset = filter_urls(url_list, urlfilter='example.com')
```

The result is sorted and deduplicated. Note the fallback: if `urlfilter`
matches nothing, `filter_urls` returns the feed-like URLs
(`feedburner`/`feedproxy`) instead of an empty list.


## Extracting links from HTML with extract_links

Use `extract_links` for general-purpose link extraction from HTML:

```python
from courlan import extract_links

html = '<html><body><a href="test/link.html">Link</a></body></html>'
links = extract_links(html, 'https://example.org')
# {'https://example.org/test/link.html'}
```

For crawl-aware extraction with robots.txt rules and link prioritization, use `filter_links` — it returns two lists separating regular links from navigation/listing links:

```python
from courlan import filter_links

html = '<a href="page1.html">Article</a><a href="/tag/listing">Tag</a>'
links, priority_links = filter_links(html, 'https://example.org', lang='en')
# links = ['https://example.org/page1.html']
# priority_links = ['https://example.org/tag/listing']
```

`extract_links` accepts `external_bool`, `no_filter`, `language`, `strict`, `trailing_slash`, `with_nav`, `redirects`, and `reference` (the former `base_url` was deprecated in 1.3.2 — passing it raises `ValueError`); `filter_links` accepts `external`, `lang`, `rules`, `strict`, and `with_nav`. See the [API reference](../api/core.md) for full signatures.


## Sampling URLs by domain with sample_urls

Sample a fixed number of URLs per domain from a larger collection:

```python
from courlan import sample_urls

urls = ['https://example.org/' + str(x) for x in range(100)]
sample = sample_urls(urls, samplesize=10)
# 10 randomly selected URLs from example.org
```

Exclude domains that are too small or too large:

```python
sample = sample_urls(urls, samplesize=5, exclude_min=2, exclude_max=1000)
```

`sample_urls` also accepts `strict` (stricter filtering on the input URLs)
and `verbose` (log the domains that were skipped).

See also `courlan --sample` in the [CLI reference](cli.md).


## Scope and crawlability checks

Determine if a link leads to another host:

```python
from courlan import is_external

is_external('https://github.com/', 'https://www.microsoft.com/')
# True

# Ignore domain suffixes — the default (treats .com and .co.uk as same)
is_external('https://google.com/', 'https://www.google.co.uk/')
# False
```

Check if a URL is usable in a crawling context:

```python
from courlan import is_not_crawlable, is_navigation_page

is_not_crawlable('https://example.com/login')
# True

is_navigation_page('https://example.com/category/myposts')
# True
```


## Cache management

Courlan uses LRU caches internally. In long-running processes, clear them periodically to reclaim memory:

```python
from courlan.meta import clear_caches
clear_caches()
```
