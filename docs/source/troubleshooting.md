# Courlan Troubleshooting & FAQ

This page lists common issues and quick fixes when using courlan.

## CLI: nothing written to output

- Ensure input file is UTF-8 encoded and contains one URL per line.
- Confirm flags: `-i INPUTFILE -o OUTPUTFILE` are provided.
- Run with `-v` for verbose logging to see why URLs were rejected.

## Slow performance / high memory

- Use `UrlStore(compressed=True)` to reduce memory use.
- For bulk processing, split the input into chunks and run multiple
  jobs (see CLI docs). Use `-p` for parallel workers in batch mode.
- Clear internal caches in long-running processes: `courlan.meta.clear_caches()`.

## Redirect checks are slow

- Redirect checks (`--redirects` / `with_redirects=True`) perform HTTP
  HEAD requests per URL and are network-bound. Only enable for small
  datasets or when resolving chains is necessary.
- Consider running redirect checks as a separate validation step on a
  filtered subset.

## UrlStore "missing" URLs

- `add_urls()` silently drops URLs rejected by filters. If URLs
  disappear, validate them with `check_url()` to see which rule
  rejected them.
- Ensure `language` and `strict` constructor options match your needs.

## Pickle / load_store warnings

- Saved state uses Python pickle. Never load pickle files from untrusted
  sources. For sharing, export with `dump_urls()` instead.

## Language detection surprises

- Language signals use path segments, query parameters, and subdomains.
  Some sites do not encode language explicitly; use `language=None` to
  disable strict filtering or add custom `TARGET_LANGS` entries.

## Tests failing locally

- Ensure dev dependencies are installed: `pip install -e '.[dev]'`.
- Run `pytest -q` to see failures. Formatting and linting issues can be
  auto-fixed with `ruff format`.

## Network timeouts and retries

- Use a downloader with retry/backoff for transient network errors.
- Keep `--redirects` off for large batches to avoid long-running HTTP
  calls.

## TypeError with language parameter

`UrlStore.add_from_html` and `filter_links` use `lang=` while most other functions use `language=`. Passing the wrong name raises a `TypeError`:

```python
# wrong — raises TypeError
store.add_from_html(html, url, language='en')

# correct
store.add_from_html(html, url, lang='en')
```

## Still stuck?

Open an issue on GitHub with: minimal reproduction, input sample, exact
command or code, and observed vs expected behavior. Include relevant
log output when possible.