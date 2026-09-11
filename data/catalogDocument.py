"""The raw catalogue document, for the modules that need fields ``ItemDefinition`` does not carry.

``data/items.py`` keeps its own loader for the fields it turns into definitions; this one serves
durability and damage, which live on the schema-2 records. A schema-1 file yields nothing here,
so a stale catalogue produces no durability and no damage rather than wrong values.
"""
import json
from pathlib import Path
from typing import Dict, Optional

SCHEMA_VERSION = 2


def _load() -> dict:
    path = Path(__file__).with_name("valheim_items.json")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if document.get("schema_version") != SCHEMA_VERSION or not isinstance(document.get("items"), list):
        return {}
    return document


_DOCUMENT = _load()
_BY_PREFAB: Dict[str, dict] = {str(r.get("prefab", "")).lower(): r for r in _DOCUMENT.get("items", ())}


def catalog_document() -> dict:
    """The loaded schema-2 document, or ``{}`` when the committed catalogue is absent or older."""
    return _DOCUMENT


def record(prefab: str) -> Optional[dict]:
    """The catalogue record for ``prefab``, matched case-insensitively, or ``None``."""
    return _BY_PREFAB.get((prefab or "").strip().lower())
