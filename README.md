# coURLan: Clean, filter, normalize, and sample URLs


[![Python package](https://img.shields.io/pypi/v/courlan.svg)](https://pypi.python.org/pypi/courlan)
[![Python versions](https://img.shields.io/pypi/pyversions/courlan.svg)](https://pypi.python.org/pypi/courlan)
[![Code Coverage](https://img.shields.io/codecov/c/github/adbar/courlan.svg)](https://codecov.io/gh/adbar/courlan)
[![Documentation](https://readthedocs.org/projects/courlan/badge/?version=latest)](https://courlan.readthedocs.io/en/latest/)


## Quickstart (1–2 minutes)

Install and try courlan from PyPI:

```bash
pip install courlan
```

Python quickstart — validate and clean a URL:

```python
from courlan import check_url
result = check_url('https://example.org/page?utm_source=twitter')
if result:
    cleaned, domain = result
    print(cleaned)  # 'https://example.org/page'
    print(domain)   # 'example.org'
```

Command-line quickstart — filter a file of URLs:

```bash
# one URL per line in urls.txt
courlan -i urls.txt -o cleaned.txt -d discarded.txt
# cleaned.txt contains accepted URLs, discarded.txt contains rejected ones
```

These examples are minimal — see the docs for advanced usage: language filtering, strict mode, sampling, and UrlStore persistence.


## Why coURLan?

> "It is important for the crawler to visit 'important' pages first,
> so that the fraction of the Web that is visited (and kept up to date)
> is more meaningful." (Cho et al. 1998)
>
> "Given that the bandwidth for conducting crawls is neither infinite
> nor free, it is becoming essential to crawl the Web in not only a
> scalable, but efficient way, if some reasonable measure of quality or
> freshness is to be maintained." (Edwards et al. 2001)

This library provides an additional "brain" for web crawling, scraping
and document management. It facilitates web navigation through a set of
filters, enhancing the quality of resulting document collections:

- Save bandwidth and processing time by steering clear of pages deemed
  low-value
- Identify specific pages based on language or text content
- Pinpoint pages relevant for efficient link gathering

Additional utilities needed include URL storage, filtering, and
deduplication.

## Features

Separate the wheat from the chaff and optimize document discovery and
retrieval:


- URL handling
   - Validation
   - Normalization
   - Sampling
- Heuristics for link filtering
   - Spam, trackers, and content-types
   - Locales and internationalization
   - Web crawling (frontier, scheduling)
- Data store specifically designed for URLs
- Usable with Python or on the command-line


**Let the coURLan fish up juicy bits for you!**

<img src="https://raw.githubusercontent.com/adbar/courlan/master/courlan_harns-march.jpg" alt="" role="presentation" style="max-width: 65%;"/>

Here is a [courlan](https://en.wiktionary.org/wiki/courlan) (source:
[Limpkin at Harn's Marsh by
Russ](https://commons.wikimedia.org/wiki/File:Limpkin,_harns_marsh_(33723700146).jpg),
CC BY 2.0).


## Installation

This package requires Python 3.10 or higher and is tested on Linux, macOS
and Windows systems.

Courlan is available on the package repository [PyPI](https://pypi.org/)
and can notably be installed with the Python package manager `pip`:

``` bash
$ pip install courlan
$ pip install --upgrade courlan # to make sure you have the latest version
$ pip install git+https://github.com/adbar/courlan.git # latest available code (see build status above)
```

The last version to support Python 3.6 and 3.7 is `courlan==1.2.0`.
The last version to support Python 3.8 and 3.9 is `courlan==1.3.2`.


## Python

Most filters revolve around the `strict` and `language` arguments.

### check_url()

All useful operations chained in `check_url(url)`:

Note: `check_url` returns `None` for rejected URLs — check the return value before unpacking.

``` python
>>> from courlan import check_url

# return url and domain name
>>> check_url('https://github.com/adbar/courlan')
('https://github.com/adbar/courlan', 'github.com')

# filter out bogus domains
>>> check_url('http://666.0.0.1/')
>>>

# language-aware filtering
>>> check_url('https://www.un.org/en/about-us', language='en')
('https://www.un.org/en/about-us', 'un.org')
>>> check_url('https://www.un.org/en/about-us', language='de')
>>>
```

For the full set of options (`strict`, `with_redirects`, `with_nav`,
`trailing_slash`, …) see the
[documentation](https://courlan.readthedocs.io/en/latest/api/core.html).

### Sampling by domain name

``` python
>>> from courlan import sample_urls
>>> my_urls = ['https://example.org/' + str(x) for x in range(100)]
>>> my_sample = sample_urls(my_urls, 10)
# optional: exclude_min=None, exclude_max=None, strict=False, verbose=False
```

See the [API reference](https://courlan.readthedocs.io/en/latest/api/index.html) for details.

### Web crawling and URL handling

Use `extract_links()` for general-purpose link extraction. For
crawl-aware extraction with robots.txt rules and link prioritization,
use `filter_links()` instead — it returns two lists: regular links and
priority (navigation) links.

``` python
>>> from courlan import extract_links
>>> doc = '<html><body><a href="test/link.html">Link</a></body></html>'
>>> extract_links(doc, "https://example.org")
{'https://example.org/test/link.html'}
```

For frontier management utilities (`is_external`, `is_navigation_page`,
`is_not_crawlable`, …) see the
[crawling guide](https://courlan.readthedocs.io/en/latest/usage/crawling.html).

### Python helpers

``` python
>>> from courlan import clean_url
>>> clean_url('HTTPS://WWW.DWDS.DE:443/')
'https://www.dwds.de'
```

For `normalize_url`, `validate_url`, `get_base_url`, `get_hostinfo`,
and other utilities see the
[API reference](https://courlan.readthedocs.io/en/latest/api/index.html).

Courlan uses an internal cache to speed up URL parsing. It can be
reset with `courlan.meta.clear_caches()`.


## UrlStore class

The `UrlStore` class allows for storing and retrieving domain-classified
URLs, where a URL like `https://example.org/path/testpage` is stored as
the path `/path/testpage` within the domain `https://example.org`:

``` python
>>> from courlan import UrlStore
>>> store = UrlStore()
>>> store.add_urls(['https://example.org/page1', 'https://example.org/page2'])
>>> store.get_url('https://example.org')
'https://example.org/page1'
>>> store.find_unvisited_urls('https://example.org')
['https://example.org/page2']
```

For the full method reference, optional settings (`compressed`, `language`,
`strict`, `verbose`), and crawl scheduling see the
[UrlStore documentation](https://courlan.readthedocs.io/en/latest/api/urlstore.html).


## Command-line

``` bash
$ courlan --inputfile url-list.txt --outputfile cleaned-urls.txt
$ courlan --help
```

See the [CLI documentation](https://courlan.readthedocs.io/en/latest/usage/cli.html) for all options.


## License

*coURLan* is distributed under the [Apache 2.0
license](https://www.apache.org/licenses/LICENSE-2.0.html).

Versions prior to v1 were under GPLv3+ license.


## Settings

`courlan` is optimized for English and German but its generic approach
is also usable in other contexts. See the
[settings reference](https://courlan.readthedocs.io/en/latest/api/settings.html)
for how to review and override filtering rules.


## Author

Initially launched to create text databases for research purposes
at the Berlin-Brandenburg Academy of Sciences (DWDS and ZDL units),
this package continues to be maintained but its future development
depends on community support.

**If you value this software or depend on it for your product, consider
sponsoring it and contributing to its codebase**. Your support
[on GitHub](https://github.com/sponsors/adbar) or [ko-fi.com](https://ko-fi.com/adbarbaresi)
will help maintain and enhance this package.
Visit the [Contributing page](https://github.com/adbar/courlan/blob/master/CONTRIBUTING.md)
for more information.

Reach out via the software repository or the [contact
page](https://adrien.barbaresi.eu/) for inquiries, collaborations, or
feedback.

For more on Courlan's software ecosystem see [this
graphic](https://github.com/adbar/trafilatura/blob/master/docs/software-ecosystem.png).


## Similar work

These Python libraries perform URL handling and normalization but do not
provide language-aware filtering, content heuristics, crawl scheduling,
or a domain-classified URL store:

-   [furl](https://github.com/gruns/furl)
-   [ural](https://github.com/medialab/ural)
-   [yarl](https://github.com/aio-libs/yarl)


## References

-   Cho, J., Garcia-Molina, H., & Page, L. (1998). Efficient crawling
    through URL ordering. *Computer networks and ISDN systems*, 30(1-7),
    161–172.
-   Edwards, J., McCurley, K. S., and Tomlin, J. A. (2001). "An
    adaptive model for optimizing performance of an incremental web
    crawler". In *Proceedings of the 10th international conference on
    World Wide Web - WWW'01*, pp. 106–113.
