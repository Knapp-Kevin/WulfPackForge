"""Hair and beard tables built from the catalog's ``Customization`` rows.

The game's "none" values are the ``HairNone`` / ``BeardNone`` prefabs. A
character that has never been customised stores an empty string, which the
editor displays as the none entry and preserves on a no-op save.
"""
from typing import Dict

from data.items import _ALL_ITEMS

HAIR_NONE = "HairNone"
BEARD_NONE = "BeardNone"

# Used only when the generated catalog is unavailable.
_FALLBACK_HAIRS = {f"Hair{i}": f"Hair {i}" for i in range(1, 38)}
_FALLBACK_BEARDS = {f"Beard{i}": f"Beard {i}" for i in range(1, 27)}


def customization_entries(prefix: str, fallback: Dict[str, str]) -> Dict[str, str]:
    """``{prefab: display_name}`` for one customization family, none entry first.

    Internal ``_2`` / ``_3`` variants are model-side alternates, not player choices.
    """
    none_key = f"{prefix}None"
    rows = {
        item.prefab: item.display_name
        for item in _ALL_ITEMS
        if item.item_type == "Customization" and item.prefab.startswith(prefix) and "_" not in item.prefab
    }
    if not rows:
        rows = dict(fallback)
    none_label = rows.pop(none_key, f"No {prefix}")
    ordered = dict(sorted(rows.items(), key=lambda pair: pair[1].lower()))
    return {none_key: none_label, **ordered}


VALHEIM_HAIRS: Dict[str, str] = customization_entries("Hair", _FALLBACK_HAIRS)
VALHEIM_BEARDS: Dict[str, str] = customization_entries("Beard", _FALLBACK_BEARDS)


def display_key(value: str, none_key: str) -> str:
    """Combo key to show for a stored value: the none entry for an empty string."""
    return none_key if value in ("", none_key) else value
