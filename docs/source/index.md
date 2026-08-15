# courlan — URL Filtering and Normalization for Python

courlan provides an additional "brain" for web crawling, scraping, and document management. It facilitates web navigation through a set of filters to enhance the quality of resulting document collections: save bandwidth by steering clear of low-value pages, identify content by language, and deduplicate URL collections at scale.

## Common tasks

| I want to… | Function / tool | Guide |
|---|---|---|
| Validate and filter a URL | `check_url` | [Python Usage](usage/python.md) |
| Clean up messy URLs | `clean_url`, `normalize_url` | [Python Usage](usage/python.md) |
| Extract links from HTML | `extract_links`, `filter_links` | [Python Usage](usage/python.md) |
| Sample N URLs per domain | `sample_urls` | [Python Usage](usage/python.md) |
| Store and track URLs for crawling | `UrlStore` | [URL Store](usage/urlstore.md) |
| Build a web crawler | `UrlStore` + `extract_links` | [Web Crawling](usage/crawling.md) |
| Filter URLs from the command line | `courlan` CLI | [CLI Reference](usage/cli.md) |
| Customize filtering rules | `courlan.settings` | [Settings](api/settings.md) |

```{toctree}
:maxdepth: 2
:caption: Contents

getting-started
usage/python
usage/urlstore
usage/crawling
usage/cli
troubleshooting
api/index

```
