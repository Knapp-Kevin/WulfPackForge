"""Inner ``Player.Save`` payload codec.

``pack_player_data_hex(unpack_player_data_hex(h)) == h`` for every supported
payload. Strings use ``surrogateescape`` so non-UTF-8 bytes survive, and the
reader refuses to return a payload that still has unconsumed bytes. Item records
are read and written by ``subscripts.itemCodec`` in the layout the payload's
``inventory_version`` declares.
"""
from subscripts.fchUtil import BinaryReader, BinaryWriter, STRING_ERRORS
from subscripts.itemCodec import read_item, write_item
from subscripts.saveErrors import SaveFormatError

__all__ = ["BinaryReader", "BinaryWriter", "STRING_ERRORS", "PlayerDataReader", "PlayerDataWriter",
           "SUPPORTED_PLAYER_DATA_VERSIONS", "payload_is_supported", "unpack_player_data_hex", "pack_player_data_hex"]

# (version, inventory_version, skill_version) triples whose layout this codec
# reads exactly. A payload outside this set still parses on a best-effort basis and is
# reported unwritable by payload_is_supported, which keeps such a character openable
# read-only. A payload whose layout this build cannot read at all fails inside the body;
# _restate_body_failure restates that failure in terms of the payload version, so the
# operator is told the save is from a newer Valheim instead of being shown a byte count.
# (29, 106, 2) is validated on real saves of container versions 40-43; (33, 109, 2) is
# validated on real Valheim 1.0 saves locally and on a synthetic fixture in CI.
SUPPORTED_PLAYER_DATA_VERSIONS = frozenset({(29, 106, 2), (33, 109, 2)})

# Layout gates, as the game declares them.
STRING_BIOMES_FROM = 33      # m_knownBiome holds strings rather than int32 flags
BUILD_UI_FROM = 33           # a trailing byte[] carrying the build UI follows eitr
USHORT_ITEM_COUNT_FROM = 108  # the inventory count is a ushort rather than an int32

READABLE_PAYLOAD_VERSIONS = frozenset(triple[0] for triple in SUPPORTED_PLAYER_DATA_VERSIONS)


def _restate_body_failure(version: int, cause: SaveFormatError) -> SaveFormatError:
    """Name the payload version when its layout is the reason the body could not be read.

    A body failure on a version this build knows is corruption, and keeps its original
    message. A body failure on a version it does not know is a newer save format, and is
    restated so the operator is told that rather than shown a byte count.
    """
    if version in READABLE_PAYLOAD_VERSIONS:
        return cause
    known = ", ".join(str(v) for v in sorted(READABLE_PAYLOAD_VERSIONS))
    return SaveFormatError(
        f"Player data version {version} could not be read by this build, which reads "
        f"version {known}. The save is from a newer Valheim."
    )


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


def new_inventory_item(prefab: str, grid_x: int, grid_y: int, durability: float) -> dict:
    """A fresh inventory record with every field the writer expects, at defaults."""
    return {
        "prefab": prefab,
        "stack": 1,
        "durability": durability,
        "grid_x": grid_x,
        "grid_y": grid_y,
        "equipped": False,
        "quality": 1,
        "variant": 0,
        "crafter_id": 0,
        "crafter_name": "",
        "custom_data": {},
        "world_level": 0,
        "picked_up": True,
    }


def _read_inventory(pkg: BinaryReader, inventory_version: int) -> list:
    count = pkg.read_ushort() if inventory_version >= USHORT_ITEM_COUNT_FROM else pkg.read_int32()
    return [read_item(pkg, inventory_version) for _ in range(count)]


def _read_biomes(pkg: BinaryReader, version: int) -> list:
    if version >= STRING_BIOMES_FROM:
        return _read_string_list(pkg)
    return [pkg.read_int32() for _ in range(pkg.read_int32())]


def _read_knowledge(pkg: BinaryReader, out: dict) -> None:
    out["known_recipes"] = _read_string_list(pkg)
    out["known_stations"] = {pkg.read_string(): pkg.read_int32() for _ in range(pkg.read_int32())}
    out["known_material"] = _read_string_list(pkg)
    out["shown_tutorials"] = _read_string_list(pkg)
    out["uniques"] = _read_string_list(pkg)
    out["trophies"] = _read_string_list(pkg)
    out["known_biomes"] = _read_biomes(pkg, out["version"])
    out["known_texts"] = _read_string_dict(pkg)


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
    try:
        out["max_health"] = pkg.read_float()
        out["health"] = pkg.read_float()
        out["max_stamina"] = pkg.read_float()
        out["time_since_death"] = pkg.read_float()
        out["guardian_power"] = pkg.read_string()
        out["guardian_power_cooldown"] = pkg.read_float()
        out["inventory_version"] = pkg.read_int32()
        out["inventory"] = _read_inventory(pkg, out["inventory_version"])
        _read_knowledge(pkg, out)
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
        if out["version"] >= BUILD_UI_FROM:
            out["build_ui"] = pkg.read_byte_array()
        pkg.require_exhausted("player data payload")
    except SaveFormatError as exc:
        raise _restate_body_failure(out["version"], exc) from exc
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


def _write_inventory(pkg: BinaryWriter, data: dict) -> None:
    inventory_version = data["inventory_version"]
    if inventory_version >= USHORT_ITEM_COUNT_FROM:
        pkg.write_ushort(len(data["inventory"]))
    else:
        pkg.write_int32(len(data["inventory"]))
    for item in data["inventory"]:
        write_item(pkg, item, inventory_version)


def _write_biomes(pkg: BinaryWriter, data: dict) -> None:
    if data["version"] >= STRING_BIOMES_FROM:
        _write_string_list(pkg, data["known_biomes"])
        return
    pkg.write_int32(len(data["known_biomes"]))
    for biome in data["known_biomes"]:
        pkg.write_int32(biome)


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
    _write_biomes(pkg, data)
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
    _write_inventory(pkg, data)
    _write_knowledge(pkg, data)
    _write_appearance(pkg, data)
    _write_progress(pkg, data)
    _write_string_dict(pkg, data["custom_data"])
    pkg.write_float(data["stamina"])
    pkg.write_float(data["max_eitr"])
    pkg.write_float(data["eitr"])
    if data["version"] >= BUILD_UI_FROM:
        pkg.write_byte_array(data.get("build_ui", b""))
    return pkg.get_bytes().hex()
