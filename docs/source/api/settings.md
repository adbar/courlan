# courlan.settings

Configuration constants for URL filtering and content detection.

```{automodule} courlan.settings
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
| `TARGET_LANGS` | `dict[str, set[str]]` | ISO 639-1 codes mapped to accepted variants (e.g. `"de"` → `{"de", "deutsch", "ger"}`) |

## Customizing settings

Settings are module-level objects loaded at import time. Patch them at runtime before any filtering calls:

```python
import courlan.settings as settings

settings.BLACKLIST.add("myservice.com")
settings.ALLOWED_PARAMS.add("story_id")
settings.TARGET_LANGS.setdefault("fr", set()).add("français")
```

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
  `{"en": {"en", "english"}, "de": {"de", "deutsch"}}`.

To inspect defaults at runtime:

```python
import courlan.settings as settings
print(settings.BLACKLIST)
print(settings.ALLOWED_PARAMS)
```

Be cautious: overly aggressive changes (e.g., emptying BLACKLIST) can
significantly alter filtering behavior.
