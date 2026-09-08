"""Valheim's stable string hash (StringExtensionMethods.GetStableHashCode).

Skill mods register a skill as ``abs(GetStableHashCode(identifier))``, so a modded skill id in a save
maps back to its identifier through this function. Signed 32-bit arithmetic as in the game.
"""


def _wrap(value: int) -> int:
    return value & 0xFFFFFFFF


def stable_hash_code(text: str) -> int:
    """Signed 32-bit hash of ``text``; stops at an embedded NUL like the original."""
    a = b = 5381
    i = 0
    while i < len(text) and text[i] != "\0":
        a = _wrap(((a << 5) + a) ^ ord(text[i]))
        if i == len(text) - 1 or text[i + 1] == "\0":
            break
        b = _wrap(((b << 5) + b) ^ ord(text[i + 1]))
        i += 2
    value = _wrap(a + b * 1566083941)
    return value - (1 << 32) if value >= (1 << 31) else value


def skill_id_for(identifier: str) -> int:
    """The skill id a mod registers for ``identifier``."""
    return abs(stable_hash_code(identifier))
