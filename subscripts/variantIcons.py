"""Per-variant icon files for an item: from the extracted game icons first, then the mod catalog.

The game stores one sprite per style ("variant") of an item such as a cape; the extraction (B11)
writes them as ``<prefab>.png, <prefab>_1.png, ...`` and records the list in its index. The count is
the only reliable source of how many styles an item has, and the picture is what tells styles apart.
"""
from pathlib import Path
from typing import List

from subscripts.iconExtraction import icon_cache_dir, load_index
from subscripts.modOverride import mod_icon_files, mod_icons_dir
from subscripts.workspace import default_workspace_root


def variant_icon_paths(prefab: str) -> List[Path]:
    """Existing PNGs for each style of ``prefab`` in variant order; empty when nothing was extracted."""
    cache_dir = icon_cache_dir(default_workspace_root())
    files = (load_index(cache_dir).get("icons") or {}).get(prefab) or []
    paths = [cache_dir / name for name in files]
    if not paths and mod_icons_dir() is not None:
        paths = [mod_icons_dir() / name for name in mod_icon_files(prefab)]
    return [path for path in paths if path.is_file()]


def variant_count(prefab: str) -> int:
    return len(variant_icon_paths(prefab))
