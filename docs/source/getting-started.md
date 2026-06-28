# Getting Started

This single guide covers both installation and a minimal, runnable Quickstart.

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

## Minimal CLI Quickstart (hands-on)

1) Create a simple input file (one URL per line):

```bash
cat > urls.txt <<'EOF'
https://github.com/adbar/courlan
https://example.com/some/page
https://another.example/path
EOF
```

2) Run a full processing pass (filters + optional redirect checks). `-i/--inputfile` and `-o/--outputfile` are required:

```bash
courlan -i urls.txt -o cleaned.txt
# or
courlan --inputfile urls.txt --outputfile cleaned.txt
```

Result: cleaned.txt contains accepted URLs (one per line). Exit code 0 indicates success.


## Troubleshooting & tips
- If the command fails, run `courlan --help` to inspect flags and check your input file encoding.
- For development, prefer `pip install -e .` so local changes take effect immediately.

## End-to-end example

Create an input file, filter it, and inspect the results:

```bash
cat > urls.txt <<'EOF'
https://www.example.com/page1
https://www.example.com/page2?utm_source=twitter
https://login.example.com/signin
https://cdn.example.com/image.jpg
https://example.org/valid-article
EOF

courlan -i urls.txt -o cleaned.txt -d discarded.txt --strict -v
```

`cleaned.txt` — accepted URLs; `discarded.txt` — rejected ones (trackers, login pages, media files, etc.).

Inspect from Python:

```python
from courlan import check_url, UrlStore

# check_url returns (url, domain) or None if rejected
result = check_url('https://example.org/valid-article')
if result:
    url, domain = result
    print(f"Accepted: {url} ({domain})")

store = UrlStore()
with open('cleaned.txt') as f:
    store.add_urls([line.strip() for line in f])

for domain in store.get_known_domains():
    print(f"{domain}: {len(store.find_known_urls(domain))} URL(s)")
```

Sample by domain for large lists:

```bash
courlan -i urls.txt -o sample.txt --sample 5 --exclude-min 2
```

## Where to go next
- **CLI Reference**: all flags and examples
- **API Reference**: programmatic integration
