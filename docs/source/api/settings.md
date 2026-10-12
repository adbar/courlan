# courlan.settings

Configuration constants for URL filtering and content detection.

```{eval-rst}
.. automodule:: courlan.settings
   :members:
   :undoc-members:
   :show-inheritance:
```

## Settings reference

| Name | Type | Purpose |
|------|------|---------|
| `BLACKLIST` | `set[str]` | Domain fragments to exclude (social media, CDNs, e-commerce, etc.) |
| `ALLOWED_PARAMS` | `set[str]` | Query parameters preserved during cleaning (content IDs, pagination) |
| `LANG_PARAMS` | `set[str]` | Query parameter names used for language detection (e.g. `lang`, `language`) |
| `TARGET_LANGS` | `dict[str, set[str]]` | ISO 639-1 codes mapped to accepted variants (e.g. `"de"` → `{"de", "deutsch", "ger"}`). Consulted **only** for the value of a `lang`/`language` query parameter — a target language absent from this mapping skips that check entirely. Path- and subdomain-based detection uses the CLDR code sets in `courlan.langcodes` instead. |

## Customizing settings

Settings are module-level objects loaded at import time. Patch them at
runtime before any filtering calls — **in place**:

```python
import courlan.settings as settings

settings.BLACKLIST.add("myservice.com")
settings.ALLOWED_PARAMS.add("story_id")
settings.TARGET_LANGS.setdefault("fr", set()).add("français")
```

Mutating methods (`.add()`, `.discard()`, `.clear()`, `.setdefault()`) are the
only ones that take effect. Rebinding does **not** work: the filter modules do
`from .settings import BLACKLIST, ...` at import time, so they hold the original
objects and `settings.BLACKLIST = set()` has no effect on filtering.

For permanent changes, edit `courlan/settings.py` directly and reinstall in editable mode (`pip install -e .`).

## Default values

The most commonly-tuned defaults live in `courlan/settings.py`. Current
values (refer to the file for the authoritative list) include:

- BLACKLIST — a set of domain fragments excluded by default (social
  media, CDNs, common platforms). Example entries: `"facebook"`,
  `"amazonaws"`, `"youtube"`.
- ALLOWED_PARAMS — query parameter names preserved during cleaning
  (content IDs, pagination), e.g. `"page"`, `"id"`, `"post"`.
- LANG_PARAMS — query parameter names used for language signals,
  typically `{ "lang", "language" }`.
- TARGET_LANGS — mapping of ISO 639-1 codes to accepted variants, e.g.
  `{"en": {"en", "english"}, "de": {"de", "deutsch"}}`. Only used for
  query-parameter language values, see the table above.

To inspect defaults at runtime:

```python
import courlan.settings as settings
print(settings.BLACKLIST)
print(settings.ALLOWED_PARAMS)
```

Be cautious: overly aggressive changes (e.g., `BLACKLIST.clear()`) can
significantly alter filtering behavior.
