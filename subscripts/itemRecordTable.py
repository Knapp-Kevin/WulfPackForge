"""Valheim 1.0.20's ``ItemData::Save`` as data: the item record the game writes, row by row.

Every row is lifted from the IL of ``assembly_valheim.dll`` (Steam build 25909357), method
``ItemData::Save``, at the offset it names (the excerpt is ``item.il`` beside the phase 49 gate
artifacts; ``ZPackage::WriteNumItems`` is ``numitems.il``). ``encode`` applies the rows and
nothing else, so its bytes are the game's for the field values it is given. The save upgrade
encodes a converted item here and accepts it only when the editor's item codec reads and
rewrites those bytes unchanged; an item the codec cannot hold as the game writes it is refused.
"""
from subscripts.binaryIO import BinaryWriter

__all__ = ["FLAG_RULES", "WRITE_ORDER", "encode"]

# (flag bit, field, predicate, IL offset): the flag byte is the OR of the bits whose predicate holds.
FLAG_RULES = (
    (1, "picked_up", "true", "11cc33"),
    (2, "equipped", "true", "11cc42"),
    (4, "quality", "not 1", "11cc51"),
    (8, "stack", "not 1", "11cc61"),
    (16, "variant", "not 0", "11cc71"),
    (32, "crafter_id", "not 0", "11cc81"),
    (64, "has_prefab", "true", "11cc23"),
    (128, "custom_data", "not empty", "11cc9c"),
)

# (field, encoding, gating flag bit or None, IL offset), in write order. u1 and u2 are conv.u1
# and conv.u2, which keep the low 8 and 16 bits; numitems is ZPackage::WriteNumItems.
WRITE_ORDER = (
    ("durability_raw", "int32", None, "11ccb4"),
    ("grid_x", "u1", None, "11ccc5"),
    ("grid_y", "u1", None, "11ccd7"),
    ("world_level", "u1", None, "11cce4"),
    ("flags", "u1", None, "11ccec"),
    ("quality", "u2", 4, "11ccfe"),
    ("stack", "u2", 8, "11cd10"),
    ("variant", "int32", 16, "11cd23"),
    ("crafter_id", "int64", 32, "11cd35"),
    ("crafter_name", "string", 32, "11cd47"),
    ("prefab_hash", "int32", 64, "11cd63"),
    ("custom_data", "numitems", 128, "11cd7d"),
    ("cheated", "u1", None, "11cde0"),
)

_PREDICATES = {
    "true": bool,
    "not 1": lambda value: value != 1,
    "not 0": lambda value: value != 0,
    "not empty": lambda value: len(value) != 0,
}


def _flags(fields: dict) -> int:
    flags = 0
    for bit, field, predicate, _offset in FLAG_RULES:
        if _PREDICATES[predicate](fields[field]):
            flags |= bit
    return flags


def _write_num_items(pkg: BinaryWriter, count: int) -> None:
    """``WriteNumItems``: one byte below 128, else ``(count >> 8) | 128`` then the low byte, each conv.u1."""
    if count < 128:
        pkg.write_byte(count & 0xFF)
        return
    pkg.write_byte(((count >> 8) | 128) & 0xFF)
    pkg.write_byte(count & 0xFF)


def _write_pairs(pkg: BinaryWriter, values: dict) -> None:
    """The custom data: ``WriteNumItems`` of the count, then each key and value."""
    _write_num_items(pkg, len(values))
    for key, item in values.items():
        pkg.write_string(key)
        pkg.write_string(item)


_ENCODERS = {
    "u1": lambda pkg, value: pkg.write_byte(int(value) & 0xFF),
    "u2": lambda pkg, value: pkg.write_ushort(int(value) & 0xFFFF),
    "int32": lambda pkg, value: pkg.write_int32(value),
    "int64": lambda pkg, value: pkg.write_long(value),
    "string": lambda pkg, value: pkg.write_string(value),
    "numitems": _write_pairs,
}


def encode(fields: dict) -> bytes:
    """The record ``ItemData::Save`` writes for these field values (``cheated`` is the bool m_cheated)."""
    values = dict(fields, flags=_flags(fields), cheated=1 if fields["cheated"] else 0)
    flags = values["flags"]
    pkg = BinaryWriter()
    for field, encoding, gate, _offset in WRITE_ORDER:
        if gate is None or flags & gate:
            _ENCODERS[encoding](pkg, values[field])
    return pkg.get_bytes()
