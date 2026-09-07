"""Maximum durability per item and quality, from the generated wiki-derived table.

``max(quality) = base + per_level * (quality - 1)``. A ``base`` of 0 means the item
never wears (crowns, the lantern, tankards); an unknown ``per_level`` only lets us
answer for quality 1. Everything else is reported as unknown so the editor falls
back to the raw value and never invents a number.
"""
import json
from pathlib import Path
from typing import Dict, Optional

DEFAULT_UNKNOWN_DURABILITY = 100.0


def _load() -> Dict[str, dict]:
    path = Path(__file__).with_name("valheim_durability.json")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if document.get("schema_version") != 1 or not isinstance(document.get("items"), dict):
        return {}
    return document["items"]


_TABLE = _load()
_LOWER = {prefab.lower(): entry for prefab, entry in _TABLE.items()}


def durability_entry(prefab: str) -> Optional[dict]:
    """Raw table entry (``base``, ``per_level``, ``levels``, ``page``) or ``None``."""
    return _LOWER.get((prefab or "").lower())


def max_durability(prefab: str, quality: int, entry: Optional[dict] = None) -> Optional[float]:
    """Real maximum at ``quality``; ``None`` when unknown or when the item never wears."""
    entry = entry if entry is not None else durability_entry(prefab)
    if not entry or not entry.get("base"):
        return None
    steps = max(0, int(quality) - 1)
    if steps == 0:
        return float(entry["base"])
    if entry.get("per_level") is None:
        return None
    return float(entry["base"]) + float(entry["per_level"]) * steps


def default_durability(prefab: str) -> float:
    """Durability for a freshly added item: the quality-1 maximum, else the historic 100.0."""
    return max_durability(prefab, 1) or DEFAULT_UNKNOWN_DURABILITY
