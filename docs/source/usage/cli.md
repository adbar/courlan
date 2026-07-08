# CLI Reference

The courlan command-line utility is installed as the `courlan` entry point.

```bash
courlan -i INPUTFILE -o OUTPUTFILE [options]
```

## Flags

| Flag | Description |
|------|-------------|
| `-i, --inputfile` | Input file — one URL per line (required) |
| `-o, --outputfile` | Output file (required) |
| `-d, --discardedfile` | Write rejected URLs to this file |
| `-v, --verbose` | Enable debug logging |
| `-p, --parallel` | Worker processes for batch mode (default: 1) |
| `--strict` | Enable more restrictive filtering |
| `-l, --language` | Keep only URLs matching this ISO 639-1 code (e.g. `en`, `de`) |
| `-r, --redirects` | Check HTTP redirects (slow — see below) |
| `--sample N` | Sample N URLs per domain instead of full processing |
| `--exclude-min N` | Skip domains with fewer than N URLs (sampling only) |
| `--exclude-max N` | Skip domains with more than N URLs (sampling only) |

## Behavior

- **Batch mode** (default): processes all URLs, writes accepted URLs to `--outputfile` and rejected ones to `--discardedfile` if specified. Parallelism controlled by `-p`.
- **Sampling mode** (`--sample`): samples N URLs per domain; `-p` is ignored.

## Complete CLI examples

### Example 1: Basic filtering with output capture

**Input file** (`urls.txt`):
```
https://www.example.com/page1
https://www.example.com/page2
https://example.com/archive
https://cdn.example.com/image.jpg
https://example.org/article
```

**Command**:
```bash
courlan -i urls.txt -o cleaned.txt -d discarded.txt
```

**Output files**:

`cleaned.txt` (accepted URLs):
```
https://www.example.com/page1
https://www.example.com/page2
https://example.org/article
```

`discarded.txt` (rejected URLs):
```
https://example.com/archive
https://cdn.example.com/image.jpg
```

### Example 2: Strict filtering with language detection

**Command**:
```bash
courlan -i urls.txt -o cleaned.txt -d discarded.txt --strict -l en
```

More restrictive filtering applied; only English URLs kept.

### Example 3: Parallel processing with verbose output

**Command** (4 worker processes, debug logging):
```bash
courlan -i urls.txt -o cleaned.txt -p 4 -v
```

Outputs debug information about each URL processing step.

### Example 4: Sampling by domain

**Input file** (`large_urls.txt`):
```
https://github.com/adbar/courlan
https://github.com/adbar/trafilatura
https://github.com/adbar/htmldate
https://example.com/page1
https://example.com/page2
https://example.com/page3
https://another.org/article
```

**Command** (2 URLs per domain, exclude domains with <2 URLs):
```bash
courlan -i large_urls.txt -o sample.txt --sample 2 --exclude-min 2
```

**Output** (`sample.txt`):
```
https://github.com/adbar/courlan
https://github.com/adbar/trafilatura
https://example.com/page1
https://example.com/page2
```

Result: 4 URLs selected (2 per domain that meets the exclusion criteria).

## Large inputs

For very large files (>1M URLs), split into chunks to limit memory usage:

```bash
split -l 100000 urls.txt urls_chunk_
for chunk in urls_chunk_*; do
    courlan -i "$chunk" -o "out_$chunk" -p 4
done
```

## Redirect checking (`-r`)

Redirect checks require an HTTP HEAD request per URL and can be slow.

**Use when:**
- You need to resolve redirect chains
- The dataset is small (<10k URLs)

**Avoid when:**
- Doing initial bulk filtering
- Processing large URL lists (>100k)
- Network latency is a concern
