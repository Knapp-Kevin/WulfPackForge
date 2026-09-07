"""Equipment roles, slots, and the game's one-item-per-slot rule.

Role and slot are computed from the catalog row plus curated prefab families;
armor values are not in the catalog (see docs/plan-qor-phase6-equipment-roles.md OQ1).
"""
from typing import List, Optional

from data.items import ItemDefinition, resolve_item

SLOT_BY_TYPE = {
    "Helmet": "head",
    "Chest": "chest",
    "Legs": "legs",
    "Shoulder": "shoulder",
    "Utility": "utility",
    "Trinket": "trinket",
}
HANDS_BY_TYPE = {
    "Shield": "left",
    "Bow": "both",
    "TwoHandedWeapon": "both",
    "TwoHandedWeaponLeft": "both",
    "OneHandedWeapon": "right",
    "Tool": "right",
    "Torch": "right",
}
WEARABLE_TYPES = frozenset(SLOT_BY_TYPE)
WEAPON_TYPES = frozenset({"OneHandedWeapon", "TwoHandedWeapon", "TwoHandedWeaponLeft", "Bow", "Tool", "Torch"})

# Enemy and NPC equipment that JotunnDoc lists as selectable but players cannot wear.
CREATURE_PREFIXES = ("Goblin", "StoneGolem_", "Charred_", "DvergerSuit", "DvergerHair", "DvergerArbalest", "DvergerStaff")
CREATURE_EXACT = frozenset({"CapeTest"})
# Hildir's outfits and festive hats: wearable, no protection value.
CLOTHING_PREFIXES = ("ArmorDress", "ArmorTunic", "ArmorHarvester", "HelmetHat")
CLOTHING_EXACT = frozenset({
    "HelmetCelebration", "HelmetMidsummerCrown", "HelmetYule", "HelmetOdin", "HelmetPointyHat",
    "HelmetStrawHat", "HelmetSweatBand", "HelmetFishingHat", "CapeOdin",
})


# Creature attack "items" JotunnDoc lists as selectable: lowercase prefabs or attack verbs
# on weapon/bow/ammo types. Player prefabs are CamelCase.
ATTACK_TOKENS = ("_Taunt", "_Call", "_Teleport", "_swing", "_throw", "_feint", "_thrust", "_volley", "_firenova")
ATTACK_TYPES = WEAPON_TYPES | {"Ammo", "AmmoNonEquipable"}
CREATURE_ATTACK_EXACT = frozenset({"PlayerUnarmed"})
INTERNAL_EXACT = frozenset({"SwordCheat", "SledgeCheat", "ShieldKnight"})


def _is_creature_attack(prefab: str, item_type: str) -> bool:
    if prefab in CREATURE_ATTACK_EXACT:
        return True
    if item_type not in ATTACK_TYPES:
        return False
    return prefab[:1].islower() or any(token in prefab for token in ATTACK_TOKENS)


def role_for(item: Optional[ItemDefinition]) -> str:
    """``creature`` / ``internal`` / ``clothing`` / ``armor`` / ``weapon`` / ``shield`` / ``accessory`` / ``none``."""
    if item is None:
        return "none"
    prefab, item_type = item.prefab, item.item_type or ""
    if prefab in INTERNAL_EXACT:
        return "internal"
    if prefab in CREATURE_EXACT or prefab.startswith(CREATURE_PREFIXES) or _is_creature_attack(prefab, item_type):
        return "creature"
    if prefab in CLOTHING_EXACT or prefab.startswith(CLOTHING_PREFIXES):
        return "clothing"
    if item_type in {"Helmet", "Chest", "Legs", "Shoulder"}:
        return "armor"
    if item_type in {"Utility", "Trinket"}:
        return "accessory"
    if item_type == "Shield":
        return "shield"
    if item_type in WEAPON_TYPES:
        return "weapon"
    return "none"


def slot_for(item: Optional[ItemDefinition]) -> Optional[str]:
    if item is None:
        return None
    return SLOT_BY_TYPE.get(item.item_type or "")


def hands_for(item: Optional[ItemDefinition]) -> Optional[str]:
    if item is None:
        return None
    return HANDS_BY_TYPE.get(item.item_type or "")


def conflicts(candidate_prefab: str, other_prefab: str) -> bool:
    """True when two equipped items could not both be worn or held at once."""
    a, b = resolve_item(candidate_prefab), resolve_item(other_prefab)
    if a is None or b is None:
        return False
    slot_a, slot_b = slot_for(a), slot_for(b)
    if slot_a and slot_a == slot_b:
        return True
    hands_a, hands_b = hands_for(a), hands_for(b)
    if not hands_a or not hands_b:
        return False
    return hands_a == hands_b or "both" in (hands_a, hands_b)


def resolve_equip(inventory: List[dict], equipped_item: dict) -> List[dict]:
    """Unequip every other item that conflicts with ``equipped_item``; return those items.

    Only the ``equipped`` flag of a conflicting item changes. Nothing happens when
    the item is not equipped or is unknown to the catalog.
    """
    if not equipped_item.get("equipped") or resolve_item(equipped_item.get("prefab", "")) is None:
        return []
    changed = []
    for other in inventory:
        if other is equipped_item or not other.get("equipped"):
            continue
        if conflicts(equipped_item["prefab"], other.get("prefab", "")):
            other["equipped"] = False
            changed.append(other)
    return changed
