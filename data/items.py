import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class ItemConstraints:
    max_stack: Optional[int] = None
    max_quality: Optional[int] = None
    variants: Optional[int] = None


@dataclass(frozen=True)
class ItemDefinition:
    prefab: str
    display_name: str
    max_stack: Optional[int] = None
    max_quality: Optional[int] = None
    variants: Optional[int] = None
    item_type: Optional[str] = None
    asset_id: Optional[str] = None

    @property
    def completion_label(self) -> str:
        return f"{self.display_name} — {self.prefab}"


def _humanize_prefab(prefab: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", prefab)
    return text.replace("_", " ").strip()


def _curated_item(prefab: str, max_stack=None, max_quality=None, variants=None, display_name=None):
    return ItemDefinition(
        prefab=prefab,
        display_name=display_name or _humanize_prefab(prefab),
        max_stack=max_stack,
        max_quality=max_quality,
        variants=variants,
    )


# Safety constraints stay deliberately curated. The generated catalog may expand names,
# types, and prefab coverage, but a source refresh cannot silently alter write limits.
_CURATED_ITEMS = [
    _curated_item("Amber", 20, 1, 1),
    _curated_item("AmberPearl", 50, 1, 1, "Amber Pearl"),
    _curated_item("AncientSeed", 50, 1, 1, "Ancient Seed"),
    _curated_item("BeechSeeds", 100, 1, 1, "Beech Seeds"),
    _curated_item("Barley", 100, 1, 1),
    _curated_item("BarleyFlour", 20, 1, 1, "Barley Flour"),
    _curated_item("BlackMetal", 30, 1, 1, "Black Metal"),
    _curated_item("Bronze", 30, 1, 1),
    _curated_item("Coal", 50, 1, 1),
    _curated_item("Copper", 30, 1, 1),
    _curated_item("FineWood", 50, 1, 1, "Fine Wood"),
    _curated_item("Flametal", 30, 1, 1),
    _curated_item("Iron", 30, 1, 1),
    _curated_item("Obsidian", 50, 1, 1),
    _curated_item("Resin", 50, 1, 1),
    _curated_item("Silver", 30, 1, 1),
    _curated_item("Stone", 50, 1, 1),
    _curated_item("Tin", 30, 1, 1),
    _curated_item("Wood", 50, 1, 1),
    _curated_item("YggdrasilWood", 50, 1, 1, "Yggdrasil Wood"),
    _curated_item("ArrowBronze", 100, 1, 1, "Bronze Arrow"),
    _curated_item("ArrowFire", 100, 1, 1, "Fire Arrow"),
    _curated_item("ArrowFlint", 100, 1, 1, "Flinthead Arrow"),
    _curated_item("ArrowFrost", 100, 1, 1, "Frost Arrow"),
    _curated_item("ArrowIron", 100, 1, 1, "Ironhead Arrow"),
    _curated_item("ArrowNeedle", 100, 1, 1, "Needle Arrow"),
    _curated_item("ArrowObsidian", 100, 1, 1, "Obsidian Arrow"),
    _curated_item("ArrowPoison", 100, 1, 1, "Poison Arrow"),
    _curated_item("ArrowSilver", 100, 1, 1, "Silver Arrow"),
    _curated_item("ArrowWood", 100, 1, 1, "Wood Arrow"),
    _curated_item("AxeStone", 1, 4, 1, "Stone Axe"),
    _curated_item("AxeFlint", 1, 4, 1, "Flint Axe"),
    _curated_item("AxeBronze", 1, 4, 1, "Bronze Axe"),
    _curated_item("AxeIron", 1, 4, 1, "Iron Axe"),
    _curated_item("AxeBlackMetal", 1, 4, 1, "Blackmetal Axe"),
    _curated_item("AtgeirBronze", 1, 4, 1, "Bronze Atgeir"),
    _curated_item("AtgeirIron", 1, 4, 1, "Iron Atgeir"),
    _curated_item("AtgeirBlackmetal", 1, 4, 1, "Blackmetal Atgeir"),
    _curated_item("Battleaxe", 1, 4, 1, "Battleaxe"),
    _curated_item("ArmorBronzeChest", 1, 4, 1, "Bronze Plate Tunic"),
    _curated_item("ArmorBronzeLegs", 1, 4, 1, "Bronze Plate Leggings"),
    _curated_item("ArmorIronChest", 1, 4, 1, "Iron Scale Mail"),
    _curated_item("ArmorIronLegs", 1, 4, 1, "Iron Greaves"),
    _curated_item("ArmorLeatherChest", 1, 4, 1, "Leather Tunic"),
    _curated_item("ArmorLeatherLegs", 1, 4, 1, "Leather Pants"),
    _curated_item("ArmorPaddedCuirass", 1, 4, 1, "Padded Cuirass"),
    _curated_item("ArmorPaddedGreaves", 1, 4, 1, "Padded Greaves"),
    _curated_item("ArmorRagsChest", 1, 2, 1, "Rag Tunic"),
    _curated_item("ArmorRagsLegs", 1, 2, 1, "Rag Pants"),
    _curated_item("ArmorTrollLeatherChest", 1, 4, 1, "Troll Leather Tunic"),
    _curated_item("ArmorTrollLeatherLegs", 1, 4, 1, "Troll Leather Pants"),
    _curated_item("ArmorWolfChest", 1, 4, 1, "Wolf Armor Chest"),
    _curated_item("ArmorWolfLegs", 1, 4, 1, "Wolf Armor Legs"),
    _curated_item("BeltStrength", 1, 1, 1, "Megingjord"),
    _curated_item("HelmetBronze", 1, 4, 1, "Bronze Helmet"),
    _curated_item("HelmetIron", 1, 4, 1, "Iron Helmet"),
    _curated_item("HelmetPadded", 1, 4, 1, "Padded Helmet"),
    _curated_item("HelmetTrollLeather", 1, 4, 1, "Troll Leather Helmet"),
    _curated_item("HelmetDrake", 1, 4, 1, "Drake Helmet"),
    _curated_item("PickaxeAntler", 1, 1, 1, "Antler Pickaxe"),
    _curated_item("PickaxeBronze", 1, 4, 1, "Bronze Pickaxe"),
    _curated_item("PickaxeIron", 1, 4, 1, "Iron Pickaxe"),
    _curated_item("ShieldWood", 1, 3, 8, "Wood Shield"),
    _curated_item("ShieldBronzeBuckler", 1, 3, 1, "Bronze Buckler"),
    _curated_item("ShieldBanded", 1, 3, 8, "Banded Shield"),
    _curated_item("ShieldBlackmetal", 1, 3, 8, "Black Metal Shield"),
    _curated_item("SwordBronze", 1, 4, 1, "Bronze Sword"),
    _curated_item("SwordIron", 1, 4, 1, "Iron Sword"),
    _curated_item("SwordSilver", 1, 4, 1, "Silver Sword"),
    _curated_item("SwordBlackmetal", 1, 4, 1, "Blackmetal Sword"),
]

CONSTRAINT_OVERRIDES: Dict[str, ItemConstraints] = {
    item.prefab.lower(): ItemConstraints(item.max_stack, item.max_quality, item.variants)
    for item in _CURATED_ITEMS
}


def _load_generated_catalog():
    path = Path(__file__).with_name("valheim_items.json")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if document.get("schema_version") != 1 or not isinstance(document.get("items"), list):
        return None
    return document


def _definition_from_record(record: dict) -> Optional[ItemDefinition]:
    prefab = str(record.get("prefab") or "").strip()
    if not prefab:
        return None

    constraints = CONSTRAINT_OVERRIDES.get(prefab.lower(), ItemConstraints())
    return ItemDefinition(
        prefab=prefab,
        display_name=str(record.get("display_name") or _humanize_prefab(prefab)).strip(),
        max_stack=constraints.max_stack,
        max_quality=constraints.max_quality,
        variants=constraints.variants,
        item_type=str(record.get("item_type") or "").strip() or None,
        asset_id=str(record.get("asset_id") or "").strip() or None,
    )


def _build_catalog():
    document = _load_generated_catalog()
    if not document:
        fallback = list(_CURATED_ITEMS)
        return None, fallback, fallback

    all_items = []
    selectable_items = []
    known_prefabs = set()

    for record in document["items"]:
        item = _definition_from_record(record)
        if not item or item.prefab.lower() in known_prefabs:
            continue
        known_prefabs.add(item.prefab.lower())
        all_items.append(item)
        if bool(record.get("selectable")):
            selectable_items.append(item)

    # Preserve curated entries even if the external generator temporarily omits one.
    for item in _CURATED_ITEMS:
        if item.prefab.lower() not in known_prefabs:
            all_items.append(item)
            selectable_items.append(item)

    return document, selectable_items, all_items


_CATALOG_DOCUMENT, ITEMS, _ALL_ITEMS = _build_catalog()
CATALOG_GAME_VERSION = _CATALOG_DOCUMENT.get("game_version") if _CATALOG_DOCUMENT else None
CATALOG_SOURCE_NAME = (
    (_CATALOG_DOCUMENT.get("source") or {}).get("name") if _CATALOG_DOCUMENT else "curated fallback"
)
CATALOG_SOURCE_URL = (
    (_CATALOG_DOCUMENT.get("source") or {}).get("url") if _CATALOG_DOCUMENT else None
)
CATALOG_ITEM_COUNT = len(_ALL_ITEMS)
CATALOG_SELECTABLE_ITEM_COUNT = len(ITEMS)

ITEMS_BY_PREFAB: Dict[str, ItemDefinition] = {item.prefab.lower(): item for item in _ALL_ITEMS}
ITEMS_BY_COMPLETION: Dict[str, ItemDefinition] = {
    item.completion_label.lower(): item for item in ITEMS
}

# Human-readable names are only resolvable when unique. Completion labels always
# include the prefab and remain unambiguous.
_display_candidates: Dict[str, ItemDefinition] = {}
_duplicate_displays = set()
for _item in ITEMS:
    _key = _item.display_name.lower()
    if _key in _display_candidates:
        _duplicate_displays.add(_key)
    else:
        _display_candidates[_key] = _item
ITEMS_BY_DISPLAY: Dict[str, ItemDefinition] = {
    key: item for key, item in _display_candidates.items() if key not in _duplicate_displays
}


def register_items(definitions: Iterable[ItemDefinition]) -> int:
    """Add definitions the catalog does not know (modded items); built-in entries are never replaced."""
    added = 0
    for item in definitions:
        key = item.prefab.lower()
        if key and key not in ITEMS_BY_PREFAB:
            ITEMS_BY_PREFAB[key] = item
            added += 1
    return added


def iter_items() -> Iterable[ItemDefinition]:
    return sorted(ITEMS, key=lambda item: (item.display_name.lower(), item.prefab.lower()))


def resolve_item(value: str) -> Optional[ItemDefinition]:
    key = (value or "").strip().lower()
    if not key:
        return None
    return ITEMS_BY_PREFAB.get(key) or ITEMS_BY_DISPLAY.get(key) or ITEMS_BY_COMPLETION.get(key)


def completion_labels():
    return [item.completion_label for item in iter_items()]


def catalog_summary() -> str:
    if CATALOG_GAME_VERSION:
        return f"Valheim {CATALOG_GAME_VERSION}: {CATALOG_SELECTABLE_ITEM_COUNT} selectable items"
    return f"Curated fallback: {CATALOG_SELECTABLE_ITEM_COUNT} selectable items"
