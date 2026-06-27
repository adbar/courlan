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

## Customizing Settings

Settings are module-level objects loaded at import time. Patch them at runtime before any filtering calls:

```python
import courlan.settings as settings

settings.BLACKLIST.add("myservice.com")
settings.ALLOWED_PARAMS.add("story_id")
settings.TARGET_LANGS["fr"].add("français")
```

For permanent changes, edit `courlan/settings.py` directly and reinstall in editable mode (`pip install -e .`).
