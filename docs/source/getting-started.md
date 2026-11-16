# Getting Started with Courlan

## Prerequisites
- Python 3.10+

Earlier releases support older Python versions:

| Python | Last supported version |
|---|---|
| 3.8 and 3.9 | `pip install courlan==1.3.2` |
| 3.6 and 3.7 | `pip install courlan==1.2.0` |


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
- For development, use `pip install -e '.[dev]'` so local changes take effect immediately and the test tools are installed. See the [Contributing page](https://github.com/adbar/courlan/blob/master/CONTRIBUTING.md).


## Where to go next
- **[Python Usage](usage/python.md)**: URL checking, cleaning, link extraction, and sampling
- **[URL Store](usage/urlstore.md)**: domain-classified URL storage
- **[Web Crawling](usage/crawling.md)**: building crawlers with courlan
- **[CLI Reference](usage/cli.md)**: all flags and examples
- **[Troubleshooting](troubleshooting.md)**: common issues and fixes
- **[API Reference](api/index.md)**: full module reference
