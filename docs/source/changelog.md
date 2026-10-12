---
myst:
  html_meta:
    description: "Courlan release history, changelog, and migration notes."
---

# Migration notes

Breaking changes, newest first. The full release history follows below.

**1.4.0**
: `UrlStore()`'s `trailing` parameter was renamed to `trailing_slash`, matching
  `check_url()` and `extract_links()`. Rename the keyword at the call site; the
  behavior is unchanged.
: Python 3.8 and 3.9 are no longer supported — 1.3.2 is the last version for them.

**1.3.2**
: `UrlStore.get_download_urls()` no longer takes `timelimit`. Drop the argument.
: `extract_links()`'s `base_url` was deprecated in favor of `url`; passing it
  now raises `ValueError`.

**1.3.0**
: Python 3.6 and 3.7 are no longer supported — 1.2.0 is the last version for them.

```{include} ../../HISTORY.md
```
