"""What the character file records about cheat state, read for display and never written.

Per the cheat-flag policy (META_LEDGER #175) the editor writes no cheat flags: the profile
flag and each item's cheat byte pass through verbatim, an item the editor adds is written
with a zero byte, and the Valheim 1.0.12 achievements bypass key is reported but never set.
Obligation carried forward: any future feature that merges or grows stacks must carry the
cheat bit into the target stack rather than drop it; no such path exists today.

Two of the game's inputs are not in this file at all - world cheat state and whether the
game runs modded - so no render of this module ever reads as an all-clear.
"""
from dataclasses import dataclass

BYPASS_KEY = "bypasscheatchecks"
CHEATED_BIT = 1
UNOBSERVABLE = "Not in this file: world cheat state, and whether the game runs modded"


@dataclass(frozen=True)
class CheatRisk:
    profile_flag: bool
    cheated_items: int
    bypass_active: bool


def _bypass_active(uniques) -> bool:
    """The game stores unique keys as ``key value`` strings and matches the key case-insensitively."""
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
    """Exactly four lines; the last names what the file cannot show."""
    return [
        "Profile cheat flag: " + ("set" if risk.profile_flag else "clear"),
        f"Items flagged as cheated: {risk.cheated_items}",
        "Achievements bypass (devcommand opt-in): " + ("active" if risk.bypass_active else "not set"),
        UNOBSERVABLE,
    ]
