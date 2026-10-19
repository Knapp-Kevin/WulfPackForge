"""The player payload after ``eitr``: the build-UI blob and, from version 34, the game's RNG state.

Valheim 1.0 (payload 33) appended the build UI's saved state as one byte array. Valheim 1.0.20
(payload 34) appends two count-prefixed int32-to-int32 dictionaries after it:
``CharacterDrop.s_pseudoCounter``, the drop pity counter, then ``Player.m_itemUpgradeSeeds``,
which feeds ``Player.GetItemUpgradeChance``. Both are opaque game state; they are carried as
ordered ``[key, value]`` pairs and never shown or edited. See
docs/research-brief-valheim-1.0.20-2026-10-18.md, finding 3.
"""
from subscripts.binaryIO import BinaryReader, BinaryWriter

__all__ = ["BUILD_UI_FROM", "RNG_STATE_FROM", "RNG_STATE_KEYS", "read_tail", "write_tail"]

BUILD_UI_FROM = 33   # a trailing byte[] carrying the build UI follows eitr
RNG_STATE_FROM = 34  # two int32 -> int32 dictionaries follow the build UI
RNG_STATE_KEYS = ("pseudo_counter", "item_upgrade_seeds")


def read_tail(pkg: BinaryReader, out: dict) -> None:
    """Read what follows ``eitr`` for the payload version already in ``out``."""
    if out["version"] >= BUILD_UI_FROM:
        out["build_ui"] = pkg.read_byte_array()
    if out["version"] >= RNG_STATE_FROM:
        for key in RNG_STATE_KEYS:
            out[key] = [[pkg.read_int32(), pkg.read_int32()] for _ in range(pkg.read_int32())]


def write_tail(pkg: BinaryWriter, data: dict) -> None:
    """Mirror of ``read_tail``; an absent dictionary is written empty."""
    if data["version"] >= BUILD_UI_FROM:
        pkg.write_byte_array(data.get("build_ui", b""))
    if data["version"] >= RNG_STATE_FROM:
        for key in RNG_STATE_KEYS:
            pairs = data.get(key, [])
            pkg.write_int32(len(pairs))
            for item_key, value in pairs:
                pkg.write_int32(item_key)
                pkg.write_int32(value)
