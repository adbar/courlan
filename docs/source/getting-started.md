# Getting Started with Courlan

## Prerequisites
- Python 3.10+


## Install

:::::{tab-set}

::::{tab-item} pip
```bash
pip install courlan
```
::::

::::{tab-item} uv
```bash
uv add courlan
```
::::

::::{tab-item} From source
```bash
git clone https://github.com/adbar/courlan.git
cd courlan
pip install -e .
```
::::

:::::


## Quick check

```python
from courlan import check_url

# returns (cleaned_url, domain) or None if rejected
check_url('https://example.org/page?utm_source=twitter')
# ('https://example.org/page', 'example.org')
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
- **[Troubleshooting](troubleshooting.md)**: common issues and fixes
- **[API Reference](api/index.md)**: full module reference
