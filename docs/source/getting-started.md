# Getting Started with Courlan

## Prerequisites
- Python 3.10+


## Install

Install the latest release from PyPI, e.g. with pip or uv:

```bash
pip install courlan
```

Or install from source for development:

```bash
git clone https://github.com/adbar/courlan.git
cd courlan
pip install -e .
```


## Quick check

```python
from courlan import check_url

# returns (cleaned_url, domain) or None if rejected
# Note: check_url returns None for rejected URLs — check the return value before unpacking.
check_url('https://example.com/page?utm_source=twitter')
# ('https://example.com/page', 'example.com')
```

From the command line:

```bash
courlan -i urls.txt -o cleaned.txt
```


## Troubleshooting
- If the command fails, run `courlan --help` to inspect flags and check your input file encoding (UTF-8 expected).
- For development, prefer `pip install -e .` so local changes take effect immediately.


## Where to go next
- **[Python Usage](usage/python.md)**: URL checking, cleaning, link extraction, and sampling
- **[URL Store](usage/urlstore.md)**: domain-classified URL storage
- **[Web Crawling](usage/crawling.md)**: building crawlers with courlan
- **[CLI Reference](usage/cli.md)**: all flags and examples
- **[API Reference](api/index.md)**: full module reference
