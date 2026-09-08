"""Curated inventory navigation: category, then subtype, then material.

Grouping is data, not widget logic, so the picker, tests, and any future
surface share one definition. Roles and slots come from ``data.equipment``.
"""
from typing import Iterable, List, Optional, Tuple

from data.equipment import role_for
from data.glyphs import glyph_for
from data.items import EXTRA_ITEMS, ITEMS, ItemDefinition

GROUPS = (
    "Weapons",
    "Bows and Ammo",
    "Shields",
    "Helmets",
    "Chest Armor",
    "Leg Armor",
    "Capes",
    "Clothing and Hats",
    "Accessories",
    "Tools",
    "Materials",
    "Food and Mead",
    "Trophies",
    "Misc",
)

MODDED = "Modded"  # items registered from a mod scan; branches by the vanilla group they would belong to

# Hair and beard rows appear in the JotunnDoc item list but are not inventory items.
EXCLUDED_TYPES = frozenset({"Customization"})

_TYPE_GROUP = {
    "OneHandedWeapon": "Weapons", "TwoHandedWeapon": "Weapons", "TwoHandedWeaponLeft": "Weapons",
    "Bow": "Bows and Ammo", "Ammo": "Bows and Ammo", "AmmoNonEquipable": "Bows and Ammo",
    "Shield": "Shields", "Helmet": "Helmets", "Chest": "Chest Armor", "Legs": "Leg Armor",
    "Shoulder": "Capes", "Utility": "Accessories", "Trinket": "Accessories",
    "Tool": "Tools", "Torch": "Tools", "Material": "Materials",
    "Consumable": "Food and Mead", "Fish": "Food and Mead", "Trophy": "Trophies", "Misc": "Misc",
}

# Progression order used to sort items within a group and to name material branches.
MATERIAL_TIERS = (
    "Wood", "Stone", "Flint", "Leather", "Troll", "Bone", "Bronze", "Copper", "Tin",
    "Iron", "Root", "Silver", "Wolf", "Fenring", "Padded", "Blackmetal", "BlackMetal",
    "Chitin", "Carapace", "Eitr", "Dvergr", "Mistlands", "Ashlands", "Flametal",
    "Fire", "Lava",
)
_TIER_INDEX = {token.lower(): index for index, token in enumerate(MATERIAL_TIERS)}
_MATERIAL_LABEL = {"BlackMetal": "Blackmetal"}
OTHER_MATERIAL = "Other"

# Named weapons carry no material in their prefab; this is the tier they are crafted at.
# Matched by prefix, so the Bleeding / Storming / Primal variants follow their base weapon.
_NAMED_TIER = {
    "Bow": "Wood", "Club": "Wood", "SledgeStagbreaker": "Wood",
    "Battleaxe": "Iron", "BowHuntsman": "Iron", "SpearElderbark": "Iron",
    "BattleaxeCrystal": "Silver", "BowDraugrFang": "Silver", "ArrowFrost": "Silver", "ArrowObsidian": "Silver",
    "MaceNeedle": "Blackmetal", "ArrowNeedle": "Blackmetal", "TurretBolt": "Blackmetal",
    "SwordMistwalker": "Eitr", "THSwordKrom": "Eitr", "AxeJotunBane": "Eitr", "AtgeirHimminAfl": "Eitr",
    "KnifeSkollAndHati": "Eitr", "BowSpineSnap": "Eitr", "CrossbowArbalest": "Eitr",
    "StaffIceShards": "Eitr", "StaffShield": "Eitr", "StaffSkeleton": "Eitr",
    "SpearSplitner": "Flametal", "SwordNiedhogg": "Flametal", "THSwordSlayer": "Flametal", "MaceEldner": "Flametal",
    "AxeBerzerkr": "Flametal", "SledgeDemolisher": "Flametal", "CrossbowRipper": "Flametal", "SwordDyrnwyn": "Flametal",
    "BattleaxeSkullSplittur": "Flametal", "StaffLightning": "Flametal", "StaffClusterbomb": "Flametal",
    "ArrowCharred": "Flametal", "BoltCharred": "Flametal",
}
_NAMED_PREFIXES = sorted(_NAMED_TIER, key=len, reverse=True)  # longest prefix wins

_SUBTYPE_LABEL = {
    "G01_sword": "Swords", "G02_axe": "Axes", "G03_mace": "Maces", "G04_knife": "Knives",
    "G05_spear": "Spears", "G06_greatsword": "Greatswords", "G07_battleaxe": "Battleaxes",
    "G08_polearm": "Polearms", "G09_sledge": "Sledges", "G10_staff": "Staves",
    "G11_bow": "Bows", "G12_crossbow": "Crossbows", "G13_arrow": "Arrows",
    "G24_bomb": "Bombs", "G25_pickaxe": "Pickaxes", "G33_fist": "Fists", "G31_tankard": "Tankards",
    "G32_fishing": "Fishing", "G34_scythe": "Scythes",
}
_SUBTYPE_ORDER = tuple(_SUBTYPE_LABEL.values()) + ("Bolts",)
_BRANCHED_GROUPS = frozenset({"Weapons", "Bows and Ammo"})


def group_for(item: Optional[ItemDefinition]) -> Optional[str]:
    """Group name for a catalog item, ``None`` when the item is not pickable."""
    if item is None or item.item_type in EXCLUDED_TYPES:
        return None
    role = role_for(item)
    if role in ("creature", "internal"):
        return None  # creature attacks and cheat items never enter a player inventory
    if role == "clothing":
        return "Clothing and Hats"
    return _TYPE_GROUP.get(item.item_type or "", "Misc")


def _named_tier(prefab: str) -> Optional[str]:
    lowered = prefab.lower()
    for prefix in _NAMED_PREFIXES:
        if lowered.startswith(prefix.lower()):
            return _NAMED_TIER[prefix]
    return None


def tier_rank(prefab: str) -> int:
    lowered = prefab.lower()
    ranks = [index for token, index in _TIER_INDEX.items() if token in lowered]
    if ranks:
        return min(ranks)
    named = _named_tier(prefab)
    return _TIER_INDEX[named.lower()] if named else len(MATERIAL_TIERS)


def material_for(item: ItemDefinition) -> Optional[str]:
    rank = tier_rank(item.prefab)
    if rank >= len(MATERIAL_TIERS):
        return None
    token = MATERIAL_TIERS[rank]
    return _MATERIAL_LABEL.get(token, token)


def _material_matches(item: ItemDefinition, material: Optional[str]) -> bool:
    if material is None:
        return True
    found = material_for(item)
    return found is None if material == OTHER_MATERIAL else found == material


def subgroup_for(item: ItemDefinition) -> Optional[str]:
    if group_for(item) not in _BRANCHED_GROUPS:
        return None
    if item.prefab.lower().startswith("bolt"):
        return "Bolts"
    return _SUBTYPE_LABEL.get(glyph_for(item)[0])


def _sorted(items: Iterable[ItemDefinition]) -> List[ItemDefinition]:
    return sorted(items, key=lambda item: (tier_rank(item.prefab), item.display_name.lower(), item.prefab.lower()))


def items_in_group(name: str) -> List[ItemDefinition]:
    if name == MODDED:
        return _sorted(item for item in EXTRA_ITEMS if group_for(item) is not None)
    return _sorted(item for item in ITEMS if group_for(item) == name)


def items_under(group: str, subgroup: Optional[str] = None, material: Optional[str] = None) -> List[ItemDefinition]:
    """Items beneath a navigation node; any level may be omitted to widen the selection."""
    if group == MODDED:
        return [item for item in items_in_group(MODDED) if subgroup is None or group_for(item) == subgroup]
    return [
        item for item in items_in_group(group)
        if (subgroup is None or subgroup_for(item) == subgroup) and _material_matches(item, material)
    ]


def navigation_tree() -> List[Tuple[str, List[Tuple[str, List[str]]]]]:
    """``[(group, [(subgroup, [material, ...]), ...]), ...]`` in display order."""
    tree = []
    for group in GROUPS:
        branches: List[Tuple[str, List[str]]] = []
        if group in _BRANCHED_GROUPS:
            present = {subgroup_for(item) for item in items_in_group(group)} - {None}
            for subgroup in [s for s in _SUBTYPE_ORDER if s in present]:
                branches.append((subgroup, _branch_materials(group, subgroup)))
        tree.append((group, branches))
    modded = items_in_group(MODDED)
    if modded:
        present = {group_for(item) for item in modded}
        tree.append((MODDED, [(group, []) for group in GROUPS if group in present]))
    return tree


def _branch_materials(group: str, subgroup: str) -> List[str]:
    """Material labels under a type, plus ``Other`` when unranked items exist; empty if only one."""
    materials, unranked = [], False
    for item in items_under(group, subgroup):
        label = material_for(item)
        unranked = unranked or label is None
        if label and label not in materials:
            materials.append(label)
    if len(materials) > 1 and unranked:
        materials.append(OTHER_MATERIAL)  # nothing hides below the type level
    return materials if len(materials) > 1 else []


def pickable_items() -> List[ItemDefinition]:
    """Every selectable catalog item that belongs to a group, sorted by display name."""
    return sorted(
        (item for item in (*ITEMS, *EXTRA_ITEMS) if group_for(item) is not None),
        key=lambda item: (item.display_name.lower(), item.prefab.lower()),
    )
