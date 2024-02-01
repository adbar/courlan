## History / Changelog


### 1.0.0

- license change from GPLv3+ to Apache 2.0 (#81)
- UrlStore: `write()` method and `load_store()` function added (#83)
- add parameter `trailing_slash` to keep of discard slashes at the end of URLs (#52)
- maintenance: fix whitespace in `clean_url()` (#77), simplify code (#79)


### 0.9.5

- IRI to URI normalization: encode path, query and fragments (#58, #60)
- normalization: strip common trackers (#65)
- new function `is_valid_url()` (#63)
- hardening of domain filter (#64)


### 0.9.4

- new UrlStore functions: `add_from_html()` (#42), `discard()` (#44), `get_unvisited_domains`
- CLI: removed `--samplesize`, use `--sample` with an integer instead (#54)
- added plausibility filter for domains/hosts (#48)
- speedups and more efficient processing (#47, #49, #50)
- fixed handling of relative URLs with @feltcat in #46
- fixed bugs and ensured compatibility (#41, #43, #51, #56)
- official support for Python 3.12


### 0.9.3

- more efficient URL parsing (#33)
- refined link extraction and link filters (#30, #36)
- more efficient normalization (#32)
- more efficient sampling strategy (#31, #35)
- added meta function to clear LRU caches (#34)
- added parallel option in command-line interface (#37, #39)
- added ``get_unvisited_domains()`` method to ``UrlStore`` (#40)


### 0.9.2

- add blogspot archives to type filter
- maintenance: upgrade ``urllib3`` and review code


### 0.9.1

- network tests: larger throughput
- UrlStore: optional compression of rules (#21), added `reset()` (#22) and `get_all_counts()` methods
- UrlStore fixes: `signal` in #18, `total_url_number`
- updated Readme


### 0.9.0

- hardening of filters and URL parses (#14)
- normalize punicode to unicode
- methods added to `UrlStore`: `get_crawl_delay()`, `print_unvisited_urls()`
- `UrlStore` now triggers exit code 1 when interrupted
- argument added to `extract_links()`: `no_filter`
- code refactoring: simplifications


### 0.8.3

- fixed bug in domain name extraction
- uniform logging parameters


### 0.8.2

- full type hinting
- maintenance: code linted


### 0.8.1

- add type annotations and check with `mypy`
- `url_filter()` function moved from Trafilatura
- code style: use `black`


### 0.8.0

- performance optimizations
- fast track for domain extraction (`extract_domain(url, fast=True)`), now taking subdomains into account


### 0.7.2

- UrlStore: threading lock and convenience functions added


### 0.7.1

- bug in sampling fixed
- UrlStore: validation by default


### 0.7.0

- UrlStore class added: data store containing URLs with relevant information
- code cleaning and maintenance (bugs, simplification)


### 0.6.0

- reviewed code base: simplicity and execution speed
- dropped support for Python 3.5


### 0.5.0

- more complex language heuristics, use langcodes
- extended blacklists and whitelists
- more precise filters and more efficient code
- support for Python 3.10


### 0.4.2

- enhanced cleaning
- fixed language filter


### 0.4.1

- keep trailing slashes to avoid redirection
- fixes: normalization and crawlable URLs


### 0.4.0

- URL manipulation tools added: extract parts, fix relative URLs
- filters added: language, navigation and crawls
- more robust link handling and extraction
- removed support for Python 3.4


### 0.3.1

- improve filter precision


### 0.3.0

- reduced dependencies: replace requests with bare urllib3, and tldextract with tld for Python 3.6 upwards
- better path and fragment normalization


### 0.2.3

- Python 3.9 compatibility
- Simplified imports
- Bug fixes


### 0.2.2

- English and German language filters
- Function to detect external links
- Support for domain blacklisting 


### 0.2.1

- Less aggressive strict filters
- CLI bug fixed


### 0.2.0

- Cleaner and more efficient filtering
- Helper functions to scrub, clean and normalize
- Removed two dependencies with more extensive usage of urllib.parse


### 0.1.0

- Cleaning and filtering targeting non-spam HTML pages with primarily text
- URL validation
- Sampling by domain name
- Command-line interface (CLI) and Python tool
