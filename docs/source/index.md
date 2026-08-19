---
myst:
  html_meta:
    description: "courlan — Python library for URL filtering, normalization, cleaning, and web crawl scheduling."
---

# courlan — URL Filtering and Normalization for Python

courlan provides an additional "brain" for web crawling, scraping, and document management. It facilitates web navigation through a set of filters to enhance the quality of resulting document collections: save bandwidth by steering clear of low-value pages, identify content by language, and deduplicate URL collections at scale.

## Common tasks

::::{grid} 2
:gutter: 3

:::{grid-item-card} Validate & filter URLs
:link: usage/python
:link-type: doc

`check_url` — validate, normalize, and filter in one call.
:::

:::{grid-item-card} Clean & normalize
:link: usage/python
:link-type: doc

`clean_url`, `normalize_url` — fix up messy URLs without full filtering.
:::

:::{grid-item-card} Extract links from HTML
:link: usage/python
:link-type: doc

`extract_links`, `filter_links` — general-purpose and crawl-aware extraction.
:::

:::{grid-item-card} Sample by domain
:link: usage/python
:link-type: doc

`sample_urls` — pick N URLs per domain from a larger collection.
:::

:::{grid-item-card} URL Store
:link: usage/urlstore
:link-type: doc

`UrlStore` — domain-classified storage with visit tracking and persistence.
:::

:::{grid-item-card} Web crawling
:link: usage/crawling
:link-type: doc

Crawl delays, robots.txt, download scheduling, and frontier management.
:::

:::{grid-item-card} Command line
:link: usage/cli
:link-type: doc

`courlan` CLI — filter and sample URL files from the terminal.
:::

:::{grid-item-card} Settings
:link: api/settings
:link-type: doc

Customize blacklists, allowed parameters, and language rules.
:::

::::

```{toctree}
:maxdepth: 2
:caption: Contents

getting-started
usage/python
usage/urlstore
usage/crawling
usage/cli
troubleshooting
changelog
api/index

```
