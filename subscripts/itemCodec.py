"""Inventory item records: the version 106 layout and the version 109 bitfield layout.

The reader always returns the dictionary the editor consumes (``prefab``, ``stack``,
``durability``, ``grid_x``, ``grid_y``, ``equipped``, ``quality``, ``variant``,
``crafter_id``, ``crafter_name``, ``custom_data``, ``world_level``, ``picked_up``). A
version 109 record adds ``_wire`` - the prefab hash, the raw durability integer and the
whole cheat byte - because those three cannot be recovered losslessly from the normalized
keys. The writer tolerates an absent ``_wire``: a fresh item is hashed from its prefab,
quantised from its durability, and written with a zero cheat byte. Flags are recomputed
from the values, as the game does; an absent quality or stack means 1.
"""
from data.itemHashes import hash_index
from subscripts.binaryIO import BinaryReader, BinaryWriter
from subscripts.stableHash import stable_hash_code

ITEM_UNKNOWN_PREFIX = "unknown#"
BITFIELD_ITEM_VERSION = 109
DURABILITY_SCALE = 100
_PICKED_UP, _EQUIPPED, _QUALITY, _STACK = 1, 2, 4, 8
_VARIANT, _CRAFTER, _PREFAB, _CUSTOM = 16, 32, 64, 128


def resolve_prefab_hash(value: int) -> str:
    """The catalogue prefab for a stable hash, or a stable non-empty ``unknown#<hash>`` token."""
    return hash_index(stable_hash_code).get(value) or f"{ITEM_UNKNOWN_PREFIX}{value}"


def _read_num_items(pkg: BinaryReader) -> int:
    first = pkg.read_byte()
    if first & 128:
        return ((first & 127) << 8) | pkg.read_byte()
    return first


def _write_num_items(pkg: BinaryWriter, count: int) -> None:
    if count < 128:
        pkg.write_byte(count)
        return
    pkg.write_byte(128 | (count >> 8))
    pkg.write_byte(count & 255)


def _read_custom_data(pkg: BinaryReader) -> dict:
    return {pkg.read_string(): pkg.read_string() for _ in range(_read_num_items(pkg))}


def _write_custom_data(pkg: BinaryWriter, values: dict) -> None:
    _write_num_items(pkg, len(values))
    for key, value in values.items():
        pkg.write_string(key)
        pkg.write_string(value)


def _read_v109_item(pkg: BinaryReader) -> dict:
    durability_raw = pkg.read_int32()
    item = {"grid_x": pkg.read_byte(), "grid_y": pkg.read_byte(), "world_level": pkg.read_byte()}
    flags = pkg.read_byte()
    item["picked_up"] = bool(flags & _PICKED_UP)
    item["equipped"] = bool(flags & _EQUIPPED)
    item["quality"] = pkg.read_ushort() if flags & _QUALITY else 1
    item["stack"] = pkg.read_ushort() if flags & _STACK else 1
    item["variant"] = pkg.read_int32() if flags & _VARIANT else 0
    item["crafter_id"] = pkg.read_long() if flags & _CRAFTER else 0
    item["crafter_name"] = pkg.read_string() if flags & _CRAFTER else ""
    prefab_hash = pkg.read_int32() if flags & _PREFAB else 0
    item["custom_data"] = _read_custom_data(pkg) if flags & _CUSTOM else {}
    item["prefab"] = resolve_prefab_hash(prefab_hash)
    item["durability"] = durability_raw / DURABILITY_SCALE
    item["_wire"] = {"prefab_hash": prefab_hash, "durability_raw": durability_raw, "cheat_flags": pkg.read_byte()}
    return item


def _read_legacy_item(pkg: BinaryReader) -> dict:
    item = {
        "prefab": pkg.read_string(),
        "stack": pkg.read_int32(),
        "durability": pkg.read_float(),
        "grid_x": pkg.read_int32(),
        "grid_y": pkg.read_int32(),
        "equipped": pkg.read_bool(),
        "quality": pkg.read_int32(),
        "variant": pkg.read_int32(),
        "crafter_id": pkg.read_long(),
        "crafter_name": pkg.read_string(),
    }
    item["custom_data"] = {pkg.read_string(): pkg.read_string() for _ in range(pkg.read_int32())}
    item["world_level"] = pkg.read_int32()
    item["picked_up"] = pkg.read_bool()
    return item


def _prefab_hash_for(item: dict) -> int:
    """An unresolved item keeps the hash it was read with; anything else is hashed from its name."""
    prefab = item.get("prefab", "")
    if prefab.startswith(ITEM_UNKNOWN_PREFIX):
        return item.get("_wire", {}).get("prefab_hash", 0)
    return stable_hash_code(prefab)


def _durability_raw_for(item: dict) -> int:
    """The stored raw integer while the durability is untouched; a fresh quantisation otherwise."""
    raw = item.get("_wire", {}).get("durability_raw")
    if raw is not None and item.get("durability") == raw / DURABILITY_SCALE:
        return raw
    return int(round(float(item.get("durability", 0.0)) * DURABILITY_SCALE))


def _item_flags(item: dict, prefab_hash: int) -> int:
    flags = 0
    if item.get("picked_up"):
        flags |= _PICKED_UP
    if item.get("equipped"):
        flags |= _EQUIPPED
    if item.get("quality", 1) != 1:
        flags |= _QUALITY
    if item.get("stack", 1) != 1:
        flags |= _STACK
    if item.get("variant", 0):
        flags |= _VARIANT
    if item.get("crafter_id", 0) or item.get("crafter_name", ""):
        flags |= _CRAFTER
    if prefab_hash:
        flags |= _PREFAB
    if item.get("custom_data"):
        flags |= _CUSTOM
    return flags


def _write_v109_item(pkg: BinaryWriter, item: dict) -> None:
    prefab_hash = _prefab_hash_for(item)
    flags = _item_flags(item, prefab_hash)
    pkg.write_int32(_durability_raw_for(item))
    pkg.write_byte(item.get("grid_x", 0))
    pkg.write_byte(item.get("grid_y", 0))
    pkg.write_byte(item.get("world_level", 0))
    pkg.write_byte(flags)
    if flags & _QUALITY:
        pkg.write_ushort(item["quality"])
    if flags & _STACK:
        pkg.write_ushort(item["stack"])
    if flags & _VARIANT:
        pkg.write_int32(item["variant"])
    if flags & _CRAFTER:
        pkg.write_long(item.get("crafter_id", 0))
        pkg.write_string(item.get("crafter_name", ""))
    if flags & _PREFAB:
        pkg.write_int32(prefab_hash)
    if flags & _CUSTOM:
        _write_custom_data(pkg, item["custom_data"])
    pkg.write_byte(item.get("_wire", {}).get("cheat_flags", 0))


def _write_legacy_item(pkg: BinaryWriter, item: dict) -> None:
    pkg.write_string(item["prefab"])
    pkg.write_int32(item["stack"])
    pkg.write_float(item["durability"])
    pkg.write_int32(item["grid_x"])
    pkg.write_int32(item["grid_y"])
    pkg.write_bool(item["equipped"])
    pkg.write_int32(item["quality"])
    pkg.write_int32(item["variant"])
    pkg.write_long(item["crafter_id"])
    pkg.write_string(item["crafter_name"])
    pkg.write_int32(len(item["custom_data"]))
    for key, value in item["custom_data"].items():
        pkg.write_string(key)
        pkg.write_string(value)
    pkg.write_int32(item["world_level"])
    pkg.write_bool(item["picked_up"])


def read_item(pkg: BinaryReader, inventory_version: int) -> dict:
    """One inventory record in the layout ``inventory_version`` declares."""
    if inventory_version >= BITFIELD_ITEM_VERSION:
        return _read_v109_item(pkg)
    return _read_legacy_item(pkg)


def write_item(pkg: BinaryWriter, item: dict, inventory_version: int) -> None:
    """Write one inventory record in the layout ``inventory_version`` declares."""
    if inventory_version >= BITFIELD_ITEM_VERSION:
        _write_v109_item(pkg, item)
    else:
        _write_legacy_item(pkg, item)
