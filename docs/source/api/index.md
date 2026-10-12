# API Reference

This section is generated from the courlan package. Click a module to jump to its reference.

```{toctree}
:maxdepth: 1
:caption: Modules

core
filters
clean
urlutils
urlstore
sampling
settings
```


## Cache management

### courlan.meta

`clear_caches()` resets the LRU caches behind `langcodes_score` and
`get_registrable_domain`, as well as `urllib.parse`'s own cache. Call it in
long-running processes to release memory.

```{eval-rst}
.. automodule:: courlan.meta
   :members:
   :undoc-members:
   :show-inheritance:
```

## Internal modules

### courlan.langcodes

CLDR-derived language and territory code sets plus the `langcodes_score`
helper, which drives path- and subdomain-based language detection.

```{eval-rst}
.. automodule:: courlan.langcodes
   :members:
   :undoc-members:
   :show-inheritance:
```

### courlan.hosts

Host utilities shared by `urlutils` and `filters`: IP-literal
canonicalization, IDNA/punycode encoding, and public-suffix (eTLD+1)
extraction via `get_registrable_domain`.

```{eval-rst}
.. automodule:: courlan.hosts
   :members:
   :undoc-members:
   :show-inheritance:
```

### courlan.network

HTTP redirect resolution used by `check_url(with_redirects=True)`.

```{eval-rst}
.. automodule:: courlan.network
   :members:
   :undoc-members:
   :show-inheritance:
```

### courlan.cli

Entry point for the `courlan` command. See the [CLI reference](../usage/cli.md) for usage.

```{eval-rst}
.. automodule:: courlan.cli
   :members:
   :undoc-members:
   :show-inheritance:
```
