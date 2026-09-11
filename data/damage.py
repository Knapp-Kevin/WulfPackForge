"""Total damage per item and quality, and the game's own bound on what counts as impossible.

``Inventory::AddItem`` marks an item cheated when its total damage exceeds 10000.0; that
constant is the only numeric definition of an impossible item in the game (research brief
2026-09-09, finding 4). The total is the catalogue's base table summed, plus ``quality - 1``
times the per-level table summed, which is how the game scales damage with quality.
"""
from typing import Optional

from data.catalogDocument import record

CHEAT_DAMAGE_THRESHOLD = 10000.0


def total_damage(prefab: str, quality: int) -> Optional[float]:
    """Damage the game computes for ``prefab`` at ``quality``; ``None`` when the catalogue carries no table."""
    entry = record(prefab)
    damage = (entry or {}).get("damage")
    if not damage:
        return None
    steps = max(0, int(quality) - 1)
    base = sum(float(v) for v in (damage.get("base") or {}).values())
    per_level = sum(float(v) for v in (damage.get("per_level") or {}).values())
    return base + per_level * steps


def exceeds_cheat_threshold(prefab: str, quality: int) -> bool:
    total = total_damage(prefab, quality)
    return total is not None and total > CHEAT_DAMAGE_THRESHOLD
