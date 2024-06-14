# coURLan: Clean, filter, normalize, and sample URLs


[![Python package](https://img.shields.io/pypi/v/courlan.svg)](https://pypi.python.org/pypi/courlan)
[![Python versions](https://img.shields.io/pypi/pyversions/courlan.svg)](https://pypi.python.org/pypi/courlan)
[![Code Coverage](https://img.shields.io/codecov/c/github/adbar/courlan.svg)](https://codecov.io/gh/adbar/courlan)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


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

<img src="https://raw.githubusercontent.com/adbar/courlan/master/courlan_harns-march.jpg" width="65%" alt="Courlan bird"/>

Here is a [courlan](https://en.wiktionary.org/wiki/courlan) (source:
[Limpkin at Harn's Marsh by
Russ](https://commons.wikimedia.org/wiki/File:Limpkin,_harns_marsh_(33723700146).jpg),
CC BY 2.0).


## Installation

This package is compatible with with all common versions of Python, it
is tested on Linux, macOS and Windows systems.

Courlan is available on the package repository [PyPI](https://pypi.org/)
and can notably be installed with the Python package manager `pip`:

``` bash
$ pip install courlan # pip3 install on systems where both Python 2 and 3 are installed
$ pip install --upgrade courlan # to make sure you have the latest version
$ pip install git+https://github.com/adbar/courlan.git # latest available code (see build status above)
```

The last version to support Python 3.6 and 3.7 is `courlan==1.2.0`.


## Python

Most filters revolve around the `strict` and `language` arguments.

### check_url()

All useful operations chained in `check_url(url)`:

``` python
>>> from courlan import check_url

# return url and domain name
>>> check_url('https://github.com/adbar/courlan')
('https://github.com/adbar/courlan', 'github.com')

# filter out bogus domains
>>> check_url('http://666.0.0.1/')
>>>

# tracker removal
>>> check_url('http://test.net/foo.html?utm_source=twitter#gclid=123')
('http://test.net/foo.html', 'test.net')

# use strict for further trimming
>>> my_url = 'https://httpbin.org/redirect-to?url=http%3A%2F%2Fexample.org'
>>> check_url(my_url, strict=True)
('https://httpbin.org/redirect-to', 'httpbin.org')

# check for redirects (HEAD request)
>>> url, domain_name = check_url(my_url, with_redirects=True)

# include navigation pages instead of discarding them
>>> check_url('http://www.example.org/page/10/', with_nav=True)

# remove trailing slash
>>> check_url('https://github.com/adbar/courlan/', trailing_slash=False)
```

Language-aware heuristics, notably internationalization in URLs, are
available in `lang_filter(url, language)`:

``` python
# optional language argument
>>> url = 'https://www.un.org/en/about-us'

# success: returns clean URL and domain name
>>> check_url(url, language='en')
('https://www.un.org/en/about-us', 'un.org')

# failure: doesn't return anything
>>> check_url(url, language='de')
>>>

# optional argument: strict
>>> url = 'https://en.wikipedia.org/'
>>> check_url(url, language='de', strict=False)
('https://en.wikipedia.org', 'wikipedia.org')
>>> check_url(url, language='de', strict=True)
>>>
```

Define stricter restrictions on the expected content type with
`strict=True`. Also blocks certain platforms and pages types crawlers
should stay away from if they don't target them explicitly and other
black holes where machines get lost.

``` python
# strict filtering: blocked as it is a major platform
>>> check_url('https://www.twitch.com/', strict=True)
>>>
```

### Sampling by domain name

``` python
>>> from courlan import sample_urls
>>> my_urls = ['https://example.org/' + str(x) for x in range(100)]
>>> my_sample = sample_urls(my_urls, 10)
# optional: exclude_min=None, exclude_max=None, strict=False, verbose=False
```

### Web crawling and URL handling

Determine if a link leads to another host:

``` python
>>> from courlan import is_external
>>> is_external('https://github.com/', 'https://www.microsoft.com/')
True
# default
>>> is_external('https://google.com/', 'https://www.google.co.uk/', ignore_suffix=True)
False
# taking suffixes into account
>>> is_external('https://google.com/', 'https://www.google.co.uk/', ignore_suffix=False)
True
```

Other useful functions dedicated to URL handling:

-   `extract_domain(url, fast=True)`: find domain and subdomain or just
    domain with `fast=False`
-   `get_base_url(url)`: strip the URL of some of its parts
-   `get_host_and_path(url)`: decompose URLs in two parts: protocol +
    host/domain and path
-   `get_hostinfo(url)`: extract domain and host info (protocol +
    host/domain)
-   `fix_relative_urls(baseurl, url)`: prepend necessary information to
    relative links

``` python
>>> from courlan import *
>>> url = 'https://www.un.org/en/about-us'

>>> get_base_url(url)
'https://www.un.org'

>>> get_host_and_path(url)
('https://www.un.org', '/en/about-us')

>>> get_hostinfo(url)
('un.org', 'https://www.un.org')

>>> fix_relative_urls('https://www.un.org', 'en/about-us')
'https://www.un.org/en/about-us'
```

Other filters dedicated to crawl frontier management:

-   `is_not_crawlable(url)`: check for deep web or pages generally not
    usable in a crawling context
-   `is_navigation_page(url)`: check for navigation and overview pages

``` python
>>> from courlan import is_navigation_page, is_not_crawlable
>>> is_navigation_page('https://www.randomblog.net/category/myposts')
True
>>> is_not_crawlable('https://www.randomblog.net/login')
True
```

### Python helpers

Helper function, scrub and normalize:

``` python
>>> from courlan import clean_url
>>> clean_url('HTTPS://WWW.DWDS.DE:80/')
'https://www.dwds.de'
```

Basic scrubbing only:

``` python
>>> from courlan import scrub_url
```

Basic canonicalization/normalization only, i.e. modifying and
standardizing URLs in a consistent manner:

``` python
>>> from urllib.parse import urlparse
>>> from courlan import normalize_url
>>> my_url = normalize_url(urlparse(my_url))
# passing URL strings directly also works
>>> my_url = normalize_url(my_url)
# remove unnecessary components and re-order query elements
>>> normalize_url('http://test.net/foo.html?utm_source=twitter&post=abc&page=2#fragment', strict=True)
'http://test.net/foo.html?page=2&post=abc'
```

Basic URL validation only:

``` python
>>> from courlan import validate_url
>>> validate_url('http://1234')
(False, None)
>>> validate_url('http://www.example.org/')
(True, ParseResult(scheme='http', netloc='www.example.org', path='/', params='', query='', fragment=''))
```

### Troubleshooting

Courlan uses an internal cache to speed up URL parsing. It can be reset
as follows:

``` python
>>> from courlan.meta import clear_caches
>>> clear_caches()
```

## UrlStore class

The `UrlStore` class allow for storing and retrieving domain-classified
URLs, where a URL like `https://example.org/path/testpage` is stored as
the path `/path/testpage` within the domain `https://example.org`. It
features the following methods:

- URL management
   - `add_urls(urls=[], appendleft=None, visited=False)`: Add a
     list of URLs to the (possibly) existing one. Optional:
     append certain URLs to the left, specify if the URLs have
     already been visited.
   - `add_from_html(htmlstring, url, external=False, lang=None, with_nav=True)`:
     Extract and filter links in a HTML string.
   - `discard(domains)`: Declare domains void and prune the store.
   - `dump_urls()`: Return a list of all known URLs.
   - `print_urls()`: Print all URLs in store (URL + TAB + visited or not).
   - `print_unvisited_urls()`: Print all unvisited URLs in store.
   - `get_all_counts()`: Return all download counts for the hosts in store.
   - `get_known_domains()`: Return all known domains as a list.
   - `get_unvisited_domains()`: Find all domains for which there are unvisited URLs.
   - `total_url_number()`: Find number of all URLs in store.
   - `is_known(url)`: Check if the given URL has already been stored.
   - `has_been_visited(url)`: Check if the given URL has already been visited.
   - `filter_unknown_urls(urls)`: Take a list of URLs and return the currently unknown ones.
   - `filter_unvisited_urls(urls)`: Take a list of URLs and return the currently unvisited ones.
   - `find_known_urls(domain)`: Get all already known URLs for the
     given domain (ex. `https://example.org`).
   - `find_unvisited_urls(domain)`: Get all unvisited URLs for the given domain.
   - `get_unvisited_domains()`: Return all domains which have not been all visited.
   - `reset()`: Re-initialize the URL store.

- Crawling and downloads
   - `get_url(domain)`: Retrieve a single URL and consider it to
     be visited (with corresponding timestamp).
   - `get_rules(domain)`: Return the stored crawling rules for the given website.
   - `store_rules(website, rules=None)`: Store crawling rules for a given website.
   - `get_crawl_delay()`: Return the delay as extracted from robots.txt, or a given default.
   - `get_download_urls(max_urls=100, time_limit=10)`: Get a list of immediately
     downloadable URLs according to the given time limit per domain.
   - `establish_download_schedule(max_urls=100, time_limit=10)`:
     Get up to the specified number of URLs along with a suitable
     backoff schedule (in seconds).
   - `download_threshold_reached(threshold)`: Find out if the
     download limit (in seconds) has been reached for one of the
     websites in store.
   - `unvisited_websites_number()`: Return the number of websites
     for which there are still URLs to visit.
   - `is_exhausted_domain(domain)`: Tell if all known URLs for
     the website have been visited.

- Persistance
   - `write(filename)`: Save the store to disk.
   - `load_store(filename)`: Read a UrlStore from disk (separate function, not class method).

- Optional settings:
   - `compressed=True`: activate compression of URLs and rules
   - `language=XX`: focus on a particular target language (two-letter code)
   - `strict=True`: stricter URL filtering
   - `verbose=True`: dump URLs if interrupted (requires use of `signal`)


## Command-line

The main fonctions are also available through a command-line utility:

``` bash
$ courlan --inputfile url-list.txt --outputfile cleaned-urls.txt
$ courlan --help
usage: courlan [-h] -i INPUTFILE -o OUTPUTFILE [-d DISCARDEDFILE] [-v]
               [-p PARALLEL] [--strict] [-l LANGUAGE] [-r] [--sample SAMPLE]
               [--exclude-max EXCLUDE_MAX] [--exclude-min EXCLUDE_MIN]

Command-line interface for Courlan

options:
  -h, --help            show this help message and exit

I/O:
  Manage input and output

  -i INPUTFILE, --inputfile INPUTFILE
                        name of input file (required)
  -o OUTPUTFILE, --outputfile OUTPUTFILE
                        name of output file (required)
  -d DISCARDEDFILE, --discardedfile DISCARDEDFILE
                        name of file to store discarded URLs (optional)
  -v, --verbose         increase output verbosity
  -p PARALLEL, --parallel PARALLEL
                        number of parallel processes (not used for sampling)

Filtering:
  Configure URL filters

  --strict              perform more restrictive tests
  -l LANGUAGE, --language LANGUAGE
                        use language filter (ISO 639-1 code)
  -r, --redirects       check redirects

Sampling:
  Use sampling by host, configure sample size

  --sample SAMPLE       size of sample per domain
  --exclude-max EXCLUDE_MAX
                        exclude domains with more than n URLs
  --exclude-min EXCLUDE_MIN
                        exclude domains with less than n URLs
```


## License

*coURLan* is distributed under the [Apache 2.0
license](https://www.apache.org/licenses/LICENSE-2.0.html).

Versions prior to v1 were under GPLv3+ license.


## Settings

`courlan` is optimized for English and German but its generic approach
is also usable in other contexts.

Details of strict URL filtering can be reviewed and changed in the file
`settings.py`. To override the default settings, clone the repository and
[re-install the package
locally](https://packaging.python.org/tutorials/installing-packages/#installing-from-a-local-src-tree).


## Contributing

[Contributions](https://github.com/adbar/courlan/blob/master/CONTRIBUTING.md)
are welcome!

Feel free to file issues on the [dedicated
page](https://github.com/adbar/courlan/issues).


## Author

Developed with practical applications of academic research in mind, this software
is part of a broader effort to derive information from web documents.
Extracting and pre-processing web texts to the exacting standards of
scientific research presents a substantial challenge.
This software package simplifies text data collection and enhances corpus quality,
it is currently used to build [text databases for research](https://www.dwds.de/d/k-web).

- Barbaresi, A. "[Trafilatura: A Web Scraping Library and
  Command-Line Tool for Text Discovery and
  Extraction](https://aclanthology.org/2021.acl-demo.15/)."
  *Proceedings of ACL/IJCNLP 2021: System Demonstrations*, 2021, pp. 122-131.

Contact: see [homepage](https://adrien.barbaresi.eu/).

Software ecosystem: see [this
graphic](https://github.com/adbar/trafilatura/blob/master/docs/software-ecosystem.png).


## Similar work

These Python libraries perform similar handling and normalization tasks
but do not entail language or content filters. They also do not
primarily focus on crawl optimization:

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
