# courlan.sampling

Sampling utilities to produce per-host URL samples.

```{automodule} courlan.sampling
:members:
:undoc-members:
:show-inheritance:
```

## Common usage

```python
from courlan import sample_urls

# Generate sample: up to 10 URLs per domain
urls = ['https://example.com/p1', 'https://example.com/p2', 'https://other.org/a']
sample = sample_urls(urls, 10)

# With exclusion filters
sample = sample_urls(urls, samplesize=5, exclude_min=2, exclude_max=100)
```

## Example: Sampling output

**Input URLs** (8 total, 3 domains):

```
https://github.com/adbar/courlan
https://github.com/adbar/trafilatura
https://github.com/adbar/htmldate
https://example.com/some/page
https://example.com/another/page
https://example.com/third/page
https://another.example/path
https://another.example/blog/post
```

**Sample with `samplesize=2`** (2 URLs per domain):

```python
from courlan import sample_urls

urls = [
    'https://github.com/adbar/courlan',
    'https://github.com/adbar/trafilatura',
    'https://github.com/adbar/htmldate',
    'https://example.com/some/page',
    'https://example.com/another/page',
    'https://example.com/third/page',
    'https://another.example/path',
    'https://another.example/blog/post',
]

sample = sample_urls(urls, samplesize=2)
# Result: 6 URLs (2 per domain)
for url in sample:
    print(url)
```

**Output**:
```
https://github.com/adbar/courlan
https://github.com/adbar/trafilatura
https://example.com/some/page
https://example.com/another/page
https://another.example/path
https://another.example/blog/post
```

**Reduction**: 8 input URLs → 6 sampled URLs (2 per domain)

For CLI sampling, see the [CLI Reference](../usage/cli.md).

