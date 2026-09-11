"""Reverse index from Valheim's stable prefab hash to the real-case prefab name.

Valheim 1.0 stores an item's identity as ``GetStableHashCode(prefab)`` rather than the
name. The index is built from ``ItemDefinition.prefab`` - never from the lowercased
``ITEMS_BY_PREFAB`` keys, because the hash is case-sensitive - and is cached on the tuple
of registered mod prefabs, which is a complete fingerprint: every registry mutation flows
through ``EXTRA_ITEMS``. The hash function is passed in so this module stays below the
``subscripts`` layer.
"""
from typing import Callable, Dict, Optional, Tuple

from data.items import EXTRA_ITEMS, ITEMS_BY_PREFAB

_cache: Optional[Tuple[tuple, object, Dict[int, str]]] = None  # (fingerprint, hasher, index)


def _fingerprint() -> tuple:
    return tuple(item.prefab for item in EXTRA_ITEMS)


def hash_index(hasher: Callable[[str], int]) -> Dict[int, str]:
    """``{hash: prefab}`` for every catalogue and registered item; rebuilt when the registry changes."""
    global _cache
    key = _fingerprint()
    if _cache is None or _cache[0] != key or _cache[1] is not hasher:
        prefabs = {item.prefab for item in ITEMS_BY_PREFAB.values()}
        _cache = (key, hasher, {hasher(prefab): prefab for prefab in prefabs})
    return _cache[2]
