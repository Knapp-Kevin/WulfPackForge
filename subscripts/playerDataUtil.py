"""Inner ``Player.Save`` payload codec.

``pack_player_data_hex(unpack_player_data_hex(h)) == h`` for every supported
payload. Strings use ``surrogateescape`` so non-UTF-8 bytes survive, and the
reader refuses to return a payload that still has unconsumed bytes.
"""
from subscripts.fchUtil import BinaryReader, BinaryWriter, STRING_ERRORS

__all__ = ["BinaryReader", "BinaryWriter", "STRING_ERRORS", "PlayerDataReader", "PlayerDataWriter",
           "SUPPORTED_PLAYER_DATA_VERSIONS", "payload_is_supported", "unpack_player_data_hex", "pack_player_data_hex"]

# (version, inventory_version, skill_version) triples whose layout this codec
# reads exactly. Any other triple parses on a best-effort basis but is not writable.
SUPPORTED_PLAYER_DATA_VERSIONS = frozenset({(29, 106, 2)})


def payload_is_supported(player_data: dict) -> bool:
    triple = (
        player_data.get("version"),
        player_data.get("inventory_version"),
        player_data.get("skill_version"),
    )
    return triple in SUPPORTED_PLAYER_DATA_VERSIONS


# Kept as names for callers that import the reader/writer types from here.
PlayerDataReader = BinaryReader
PlayerDataWriter = BinaryWriter


def _read_string_dict(pkg: BinaryReader) -> dict:
    return {pkg.read_string(): pkg.read_string() for _ in range(pkg.read_int32())}


def _read_string_list(pkg: BinaryReader) -> list:
    return [pkg.read_string() for _ in range(pkg.read_int32())]


def _read_item(pkg: BinaryReader) -> dict:
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
    item["custom_data"] = _read_string_dict(pkg)
    item["world_level"] = pkg.read_int32()
    item["picked_up"] = pkg.read_bool()
    return item


def _read_appearance(pkg: BinaryReader, out: dict) -> None:
    out["beard"] = pkg.read_string()
    out["hair"] = pkg.read_string()
    out["skin_color"] = [pkg.read_float(), pkg.read_float(), pkg.read_float()]
    out["hair_color"] = [pkg.read_float(), pkg.read_float(), pkg.read_float()]
    out["model_index"] = pkg.read_int32()


def unpack_player_data_hex(hex_string: str) -> dict:
    """Parse the nested Player.Save payload into a dictionary."""
    if not hex_string:
        return {}
    raw_bytes = bytes.fromhex(hex_string)
    pkg = BinaryReader(raw_bytes)
    out = {"version": pkg.read_int32()}
    out["max_health"] = pkg.read_float()
    out["health"] = pkg.read_float()
    out["max_stamina"] = pkg.read_float()
    out["time_since_death"] = pkg.read_float()
    out["guardian_power"] = pkg.read_string()
    out["guardian_power_cooldown"] = pkg.read_float()
    out["inventory_version"] = pkg.read_int32()
    out["inventory"] = [_read_item(pkg) for _ in range(pkg.read_int32())]
    out["known_recipes"] = _read_string_list(pkg)
    out["known_stations"] = {pkg.read_string(): pkg.read_int32() for _ in range(pkg.read_int32())}
    out["known_material"] = _read_string_list(pkg)
    out["shown_tutorials"] = _read_string_list(pkg)
    out["uniques"] = _read_string_list(pkg)
    out["trophies"] = _read_string_list(pkg)
    out["known_biomes"] = [pkg.read_int32() for _ in range(pkg.read_int32())]
    out["known_texts"] = _read_string_dict(pkg)
    _read_appearance(pkg, out)
    out["foods"] = [{"name": pkg.read_string(), "time": pkg.read_float()} for _ in range(pkg.read_int32())]
    out["skill_version"] = pkg.read_int32()
    out["skills"] = [
        {"id": pkg.read_int32(), "level": pkg.read_float(), "xp": pkg.read_float()}
        for _ in range(pkg.read_int32())
    ]
    out["custom_data"] = _read_string_dict(pkg)
    out["stamina"] = pkg.read_float()
    out["max_eitr"] = pkg.read_float()
    out["eitr"] = pkg.read_float()
    pkg.require_exhausted("player data payload")
    return out


def _write_string_dict(pkg: BinaryWriter, values: dict) -> None:
    pkg.write_int32(len(values))
    for key, value in values.items():
        pkg.write_string(key)
        pkg.write_string(value)


def _write_string_list(pkg: BinaryWriter, values: list) -> None:
    pkg.write_int32(len(values))
    for value in values:
        pkg.write_string(value)


def _write_item(pkg: BinaryWriter, item: dict) -> None:
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
    _write_string_dict(pkg, item["custom_data"])
    pkg.write_int32(item["world_level"])
    pkg.write_bool(item["picked_up"])


def _write_appearance(pkg: BinaryWriter, data: dict) -> None:
    pkg.write_string(data["beard"])
    pkg.write_string(data["hair"])
    for component in data["skin_color"]:
        pkg.write_float(component)
    for component in data["hair_color"]:
        pkg.write_float(component)
    pkg.write_int32(data["model_index"])


def _write_knowledge(pkg: BinaryWriter, data: dict) -> None:
    _write_string_list(pkg, data["known_recipes"])
    pkg.write_int32(len(data["known_stations"]))
    for key, value in data["known_stations"].items():
        pkg.write_string(key)
        pkg.write_int32(value)
    _write_string_list(pkg, data["known_material"])
    _write_string_list(pkg, data["shown_tutorials"])
    _write_string_list(pkg, data["uniques"])
    _write_string_list(pkg, data["trophies"])
    pkg.write_int32(len(data["known_biomes"]))
    for biome in data["known_biomes"]:
        pkg.write_int32(biome)
    _write_string_dict(pkg, data["known_texts"])


def _write_progress(pkg: BinaryWriter, data: dict) -> None:
    pkg.write_int32(len(data["foods"]))
    for food in data["foods"]:
        pkg.write_string(food["name"])
        pkg.write_float(food["time"])
    pkg.write_int32(data["skill_version"])
    pkg.write_int32(len(data["skills"]))
    for skill in data["skills"]:
        pkg.write_int32(skill["id"])
        pkg.write_float(skill["level"])
        pkg.write_float(skill["xp"])


def pack_player_data_hex(data: dict) -> str:
    """Serialize the player payload dictionary back into a hex string."""
    pkg = BinaryWriter()
    pkg.write_int32(data["version"])
    pkg.write_float(data["max_health"])
    pkg.write_float(data["health"])
    pkg.write_float(data["max_stamina"])
    pkg.write_float(data["time_since_death"])
    pkg.write_string(data["guardian_power"])
    pkg.write_float(data["guardian_power_cooldown"])
    pkg.write_int32(data["inventory_version"])
    pkg.write_int32(len(data["inventory"]))
    for item in data["inventory"]:
        _write_item(pkg, item)
    _write_knowledge(pkg, data)
    _write_appearance(pkg, data)
    _write_progress(pkg, data)
    _write_string_dict(pkg, data["custom_data"])
    pkg.write_float(data["stamina"])
    pkg.write_float(data["max_eitr"])
    pkg.write_float(data["eitr"])
    return pkg.get_bytes().hex()
