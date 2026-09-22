"""Read-only achievement eligibility evidence from a Valheim character save.

WulfPackForge never treats a clear profile flag as proof that achievements are enabled.
Valheim 1.0 can also block achievements because of cheated inventory, cheated worlds,
world modifiers, modded runtime state, and other live state that is not represented in
this character file.

The editor writes no cheat state intentionally. The profile flag and each item's cheat
byte pass through verbatim, and a newly created item is written with a zero cheat byte.
Valheim 1.0.15 also has a known game bug that can incorrectly mark some items as cheated,
so an item marker is evidence of current achievement risk, not proof of player intent.
"""
from dataclasses import dataclass

BYPASS_KEY = "bypasscheatchecks"
CHEATED_BIT = 1
UNOBSERVABLE = (
    "Not in this file: world cheat state, world modifiers, and live mod/runtime state"
)
ITEM_BUG_NOTE = (
    "Valheim 1.0.15 note: the game can incorrectly mark some items as cheated; Iron Gate has a fix pending"
)


@dataclass(frozen=True)
class CheatRisk:
    profile_flag: bool
    cheated_items: int
    bypass_active: bool


def _bypass_active(uniques) -> bool:
    """Recognize the stored achievement-override marker without ever creating it."""
    for entry in uniques or ():
        key, _, value = str(entry).partition(" ")
        if key.lower() == BYPASS_KEY and value.strip() == "1":
            return True
    return False


def _item_cheated(item: dict) -> bool:
    return bool(item.get("_wire", {}).get("cheat_flags", 0) & CHEATED_BIT)


def from_character(root: dict, payload: dict) -> CheatRisk:
    root, payload = root or {}, payload or {}
    return CheatRisk(
        profile_flag=bool(root.get("used_cheats", False)),
        cheated_items=sum(1 for item in payload.get("inventory") or () if _item_cheated(item)),
        bypass_active=_bypass_active(payload.get("uniques")),
    )


def risk_lines(risk: CheatRisk) -> list:
    """Report observable evidence without claiming overall achievement eligibility."""
    return [
        "Permanent character cheat flag: " + ("set" if risk.profile_flag else "clear"),
        f"Inventory items currently marked cheated: {risk.cheated_items}",
        "Achievement override marker: " + ("present" if risk.bypass_active else "not present"),
        UNOBSERVABLE,
        ITEM_BUG_NOTE,
        "Result: this character file alone cannot prove that achievements are enabled",
    ]
