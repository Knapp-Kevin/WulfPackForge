"""Build the item catalogue from the installed game: bundles for item data, resources.assets for names.

Everything except the two UnityPy walks is a pure function over dictionaries and strings, so
the record shape, the filtering, the cross-check and the document assembly are tested without
the game. UnityPy is the optional dependency icon extraction already declares; its absence is
reported by name rather than by traceback.
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from subscripts.iconExtraction import bundles_dir, extraction_available

SCHEMA_VERSION = 2
MIN_ITEMS, MIN_SELECTABLE = 300, 200
ITEM_TYPES = {
    0: "None", 1: "Material", 2: "Consumable", 3: "OneHandedWeapon", 4: "Bow", 5: "Shield", 6: "Helmet",
    7: "Chest", 9: "Ammo", 10: "Customization", 11: "Legs", 12: "Hands", 13: "Trophy", 14: "TwoHandedWeapon",
    15: "Torch", 16: "Misc", 17: "Shoulder", 18: "Utility", 19: "Tool", 20: "Attach_Atgeir", 21: "Fish",
    22: "TwoHandedWeaponLeft", 23: "AmmoNonEquipable", 24: "Trinket",
}
# The keys GetTotalDamage sums: the generic damage plus every typed damage; m_nonPlayer is not one of them.
DAMAGE_KEYS = ("damage", "blunt", "slash", "pierce", "chop", "pickaxe", "fire", "frost", "lightning", "poison", "spirit")
_DUPLICATE_SUFFIX = re.compile(r" \(\d+\)$")
_TOKEN_PREFIX = "$"
# Attack prefabs of the frozen Greydwarf shaman variant: the only two ItemDrop objects the game's
# own item registry (and JotunnDoc) leave out. Creature attacks in general are items with plain
# (untokenised) names and stay in, as they always have.
EXCLUDED_PREFABS = frozenset({"Greydwarf_shaman_attack_frozen", "Greydwarf_shaman_heal_frozen"})
# NPC-held copies of player equipment added in 1.0 (53 prefabs). They share the player items'
# names and icons, so offering them in the picker would show every one of those items twice.
# They stay in the catalogue (a save can hold them) but are not selectable.
NPC_VARIANT_PREFIXES = ("FW_", "SP_")


def english_names(csv_text: str) -> Dict[str, str]:
    """Token (without ``$``) to English, from a localisation CSV whose second column is English."""
    names: Dict[str, str] = {}
    for row in csv.reader(io.StringIO(csv_text)):
        if len(row) >= 2 and row[0] and not row[0].startswith("﻿"):
            names.setdefault(row[0], row[1])
    return names


def _damage_table(values: dict) -> Dict[str, float]:
    return {key: float(values.get(f"m_{key}", 0.0)) for key in DAMAGE_KEYS if float(values.get(f"m_{key}", 0.0))}


def _humanize(prefab: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", prefab).replace("_", " ").strip()


def item_record(prefab: str, shared: dict, english: Dict[str, str]) -> Optional[dict]:
    """One schema-2 record, or None for a duplicate ``Name (n)`` object or an excluded prefab."""
    if _DUPLICATE_SUFFIX.search(prefab) or prefab in EXCLUDED_PREFABS:
        return None
    name = str(shared.get("m_name") or "")
    if name.startswith(_TOKEN_PREFIX):
        name = english.get(name[1:]) or _humanize(prefab)
    record = {
        "prefab": prefab,
        "display_name": name or _humanize(prefab),
        "item_type": ITEM_TYPES.get(int(shared.get("m_itemType", 0)), "None"),
        "asset_id": None,
        "selectable": bool(shared.get("m_icons")) and not prefab.startswith(NPC_VARIANT_PREFIXES),
        "limits": {"max_stack": int(shared.get("m_maxStackSize", 1)), "max_quality": int(shared.get("m_maxQuality", 1)),
                   "variants": int(shared.get("m_variants", 0))},
    }
    if shared.get("m_useDurability"):
        record["durability"] = {"max": float(shared.get("m_maxDurability", 0.0)),
                                "per_level": float(shared.get("m_durabilityPerLevel", 0.0))}
    base, per_level = _damage_table(shared.get("m_damages") or {}), _damage_table(shared.get("m_damagesPerLevel") or {})
    if base or per_level:
        record["damage"] = {"base": base, "per_level": per_level}
    return record


def build_document(records: Iterable[dict], game_version: str, build_id: Optional[int], source_note: str = "") -> dict:
    items = sorted((r for r in records if r), key=lambda r: r["prefab"].lower())
    selectable = sum(1 for r in items if r["selectable"])
    if len(items) < MIN_ITEMS or selectable < MIN_SELECTABLE:
        raise RuntimeError(f"Parsed suspiciously small catalog: {len(items)} rows, {selectable} selectable. Refusing to publish it.")
    return {
        "schema_version": SCHEMA_VERSION, "game_version": game_version, "build_id": build_id,
        "source": {"name": "Installed Valheim game data (ItemDrop shared data and localization assets)",
                   "url": "", "note": source_note or "Generated from the player's own installation by tools/catalogFromGame.py."},
        "item_count": len(items), "selectable_item_count": selectable, "items": items,
    }


def cross_check(document: dict, jotunn: dict) -> List[str]:
    """Human-readable differences against a JotunnDoc document; empty when sets, types and selectability agree."""
    ours = {r["prefab"]: r for r in document["items"]}
    theirs = {r["prefab"]: r for r in jotunn["items"]}
    lines = [f"only in the game data: {p}" for p in sorted(ours.keys() - theirs.keys())]
    lines += [f"only in JotunnDoc: {p}" for p in sorted(theirs.keys() - ours.keys())]
    for prefab in sorted(ours.keys() & theirs.keys()):
        mine, other = ours[prefab], theirs[prefab]
        if mine["item_type"] != other["item_type"]:
            lines.append(f"type differs for {prefab}: game {mine['item_type']}, JotunnDoc {other['item_type']}")
        if bool(mine["selectable"]) != bool(other["selectable"]):
            lines.append(f"selectable differs for {prefab}: game {mine['selectable']}, JotunnDoc {other['selectable']}")
    return lines


def merge_asset_ids(document: dict, jotunn: dict) -> dict:
    """The same document with JotunnDoc asset ids copied onto matching prefabs."""
    ids = {r["prefab"]: r.get("asset_id") for r in jotunn["items"]}
    for record in document["items"]:
        if ids.get(record["prefab"]):
            record["asset_id"] = ids[record["prefab"]]
    return document


def steam_build_id(game_dir: Path) -> Optional[int]:
    """The Steam ``buildid`` from the app manifest two folders above the game, when present."""
    manifest = Path(game_dir).parent.parent / "appmanifest_892970.acf"
    if not manifest.is_file():
        return None
    match = re.search(r'"buildid"\s+"(\d+)"', manifest.read_text(encoding="utf-8", errors="replace"))
    return int(match.group(1)) if match else None


def _require_unitypy():
    if not extraction_available():
        raise RuntimeError("Generating from the game needs the optional UnityPy package: pip install -r requirements-optional.txt")
    import UnityPy  # noqa: WPS433 optional dependency, imported only here
    return UnityPy


def _shared_of(game_object, deref: Callable) -> Optional[dict]:
    for component in game_object.m_Components:
        try:
            behaviour = deref(component.component if hasattr(component, "component") else component)
            if behaviour is None or behaviour.type.name != "MonoBehaviour":
                continue
            tree = behaviour.read_typetree()
        except Exception:  # unreadable component: not the one we want
            continue
        if "m_itemData" in tree:
            return tree["m_itemData"]["m_shared"]
    return None


def shared_items(game_dir: Path) -> Dict[str, dict]:
    """Prefab name to ``m_shared`` for every game object carrying an ItemDrop, read from the bundles."""
    unitypy = _require_unitypy()
    environment = unitypy.load(str(bundles_dir(game_dir)))
    found: Dict[str, dict] = {}

    def deref(pointer):
        try:
            return pointer.deref()
        except Exception:
            return None

    for obj in environment.objects:
        if obj.type.name != "GameObject":
            continue
        try:
            game_object = obj.read()
        except Exception:
            continue
        if game_object.m_Name in found:
            continue
        shared = _shared_of(game_object, deref)
        if shared is not None:
            found[game_object.m_Name] = shared
    return found


def localisation_csv(game_dir: Path) -> str:
    """Every ``localization_*`` text asset in resources.assets, concatenated."""
    unitypy = _require_unitypy()
    environment = unitypy.load(str(Path(game_dir) / "valheim_Data" / "resources.assets"))
    parts = []
    for obj in environment.objects:
        if obj.type.name != "TextAsset":
            continue
        asset = obj.read()
        if str(asset.m_Name).startswith("localization"):
            script = asset.m_Script
            parts.append(script if isinstance(script, str) else bytes(script).decode("utf-8", "replace"))
    return "\n".join(parts)


def generate(game_dir: Path, game_version: str) -> dict:
    """The schema-2 document for the installed game at ``game_dir``."""
    english = english_names(localisation_csv(game_dir))
    records = (item_record(prefab, shared, english) for prefab, shared in shared_items(game_dir).items())
    return build_document(records, game_version, steam_build_id(game_dir))
