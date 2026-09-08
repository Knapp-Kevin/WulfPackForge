"""Modded item names and icons from the asset bundles embedded in plugin DLLs (optional UnityPy)."""
import importlib.util
import io
import logging
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from subscripts.iconExtraction import _unitypy_deref, _unitypy_icon
from subscripts.modScan import display_name

logger = logging.getLogger(__name__)

BUNDLE_MAGIC = b"UnityFS\x00"
# Valheim's ItemDrop.ItemData.ItemType enum, as the catalog names them.
ITEM_TYPES = {1: "Material", 2: "Consumable", 3: "OneHandedWeapon", 4: "Bow", 5: "Shield", 6: "Helmet", 7: "Chest",
              9: "Ammo", 10: "Customization", 11: "Legs", 12: "Hands", 13: "Trophy", 14: "TwoHandedWeapon",
              15: "Torch", 16: "Misc", 17: "Shoulder", 18: "Utility", 19: "Tool", 20: "Attach_Atgeir", 21: "Fish",
              22: "TwoHandedWeaponLeft", 23: "AmmoNonEquipable", 24: "Trinket"}
Progress = Optional[Callable[[str, int, int], None]]


def items_available() -> bool:
    return importlib.util.find_spec("UnityPy") is not None


def embedded_bundle_offsets(data: bytes) -> List[int]:
    offsets, start = [], 0
    while True:
        index = data.find(BUNDLE_MAGIC, start)
        if index < 0:
            return offsets
        offsets.append(index)
        start = index + len(BUNDLE_MAGIC)


def _item_data(components, deref) -> Optional[dict]:
    for component in components:
        try:
            behaviour = deref(component.component if hasattr(component, "component") else component)
            if behaviour is None or behaviour.type.name != "MonoBehaviour":
                continue
            tree = behaviour.read_typetree()
        except Exception:
            continue
        if "m_itemData" in tree:
            return tree["m_itemData"]["m_shared"]
    return None


def collect_mod_items(objects: Iterable, deref, resolve_icon) -> Dict[str, Tuple[dict, list]]:
    """Every ItemDrop prefab in a bundle: prefab -> (shared item data, icon sprites)."""
    found: Dict[str, Tuple[dict, list]] = {}
    for obj in objects:
        if obj.type.name != "GameObject":
            continue
        try:
            game_object = obj.read()
        except Exception:
            continue
        if game_object.m_Name in found:
            continue
        shared = _item_data(game_object.m_Components, deref)
        if shared is None:
            continue
        sprites = [s for s in (resolve_icon(ref, obj) for ref in shared.get("m_icons") or []) if s is not None]
        found[game_object.m_Name] = (shared, sprites)
    return found


def item_record(prefab: str, shared: dict, texts: Dict[str, str], icon_files: List[str]) -> dict:
    return {
        "display_name": display_name(shared.get("m_name"), texts, prefab),
        "item_type": ITEM_TYPES.get(shared.get("m_itemType"), "Misc"),
        "max_stack": shared.get("m_maxStackSize") or 1,
        "max_quality": shared.get("m_maxQuality") or 1,
        "variants": shared.get("m_variants") or 1,
        "icons": icon_files,
    }


def _save_icons(prefab: str, sprites: list, icons_dir: Path) -> List[str]:
    files = []
    for index, sprite in enumerate(sprites):
        target = icons_dir / (f"{prefab}.png" if index == 0 else f"{prefab}_{index}.png")
        try:
            sprite.image.save(target)
            files.append(target.name)
        except Exception:
            logger.exception("Could not save mod icon %s", target)
    return files


def _bundle_items(dll: Path, texts: Dict[str, str], icons_dir: Path, items: Dict[str, dict]) -> Tuple[int, List[str]]:
    import UnityPy  # optional dependency

    data = dll.read_bytes()
    icons, errors = 0, []
    for offset in embedded_bundle_offsets(data):
        try:
            environment = UnityPy.load(io.BytesIO(data[offset:]))
        except Exception as exc:
            errors.append(f"{dll.name}@{offset}: {type(exc).__name__}")
            continue
        for prefab, (shared, sprites) in collect_mod_items(environment.objects, _unitypy_deref, _unitypy_icon).items():
            if prefab in items:
                continue
            files = _save_icons(prefab, sprites, icons_dir)
            icons += len(files)
            items[prefab] = dict(item_record(prefab, shared, texts, files), source=dll.name)
    return icons, errors


def scan_items(dlls: Iterable[Path], texts: Dict[str, str], icons_dir: Path, progress: Progress = None):
    """Walk every embedded bundle; returns (items, icon count, errors)."""
    dlls = list(dlls)
    Path(icons_dir).mkdir(parents=True, exist_ok=True)
    items: Dict[str, dict] = {}
    icons, errors = 0, []
    for done, dll in enumerate(dlls, start=1):
        try:
            found, bundle_errors = _bundle_items(dll, texts, Path(icons_dir), items)
        except OSError as exc:
            found, bundle_errors = 0, [f"{dll.name}: {exc}"]
        icons += found
        errors.extend(bundle_errors)
        if progress:
            progress("Reading mod items", done, len(dlls))
    return items, icons, errors
