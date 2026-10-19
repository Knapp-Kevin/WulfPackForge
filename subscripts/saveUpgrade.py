"""The save upgrade: a readable older character, converted to the current Valheim format.

Valheim 1.0.20 writes container 47, player data 34 and item records 110. Every save the
editor writes is in that format, so a character read at container 40-43 or 46 is converted
when it is opened, by the part of the game's own migration that differs by version:

- container 40-43: the flat statistics become record 0 of ten, padded to the 205 entries
  the game writes, and the old dictionaries move into record 0, the enemy dictionary into
  group 0 of five; container 46 keeps its records, fitted to 205 entries;
- payload 29: each integer known biome becomes ``$biome_`` plus its lowercased enum name,
  duplicates collapsing; the build-UI blob is empty; payload 33 keeps its blob; both gain
  the two version 34 dictionaries, empty unless already present;
- items: each item's in-memory values after the game's load (for 106, the legacy record's
  values with the prefab hashed, the durability as ``conv.i4(m_durability * 100f)`` and no
  cheat state; for 109, the record's values with the cheat bit not applied, because 1.0.20
  applies it only from 110) are encoded by ``itemRecordTable``, which is ``ItemData::Save``
  lifted row by row from the IL; an item with an empty prefab is dropped, as
  ``Inventory::LoadOld`` skips it.

An item is accepted only when the editor's item codec reads the encoded record and writes it
back byte for byte, so every accepted item is the record the game's writer produces for those
values; any other item is refused. A 1.0 item's durability is its stored integer: the game
re-derives it through a float on every load, at every version (``ItemData::Load``), and may
then write one hundredth less, which the editor leaves to the game as it does on any save. The other refusals are inputs whose conversion the evidence does not determine: a
statistics array longer than 205 entries, a known-biome integer that is not a named ``Biome``
value (``Biome`` is a flags enum, and the editor does not reproduce how the runtime formats
other values), and a legacy durability whose truncation differs between a float32 and a wider
product (the IL admits both) or that overflows. Refusals raise ``SaveFormatError``. The game's
every-load normalisation (unknown prefabs dropped, stacks clamped, invalid variants reset,
over-threshold items flagged) is not reproduced: the game re-applies it on every load, and
invariant 8 keeps modded data. The function is pure over values and records what it did as
``payload["_upgrade"]``, which no writer serializes. See
docs/research-brief-valheim-1.0.20-2026-10-18.md, findings 9-13.
"""
import copy
import math
import struct

from subscripts.binaryIO import BinaryReader, BinaryWriter
from subscripts.cheatRisk import CHEATED_BIT
from subscripts.fchUtil import CURRENT_CHARACTER_SAVE_VERSION, CURRENT_FORMAT_GAME_VERSION, READABLE_CHARACTER_SAVE_VERSIONS
from subscripts.itemCodec import read_item, write_item
from subscripts.itemRecordTable import encode
from subscripts.playerDataUtil import pack_player_data_hex, payload_is_supported, unpack_player_data_hex
from subscripts.saveErrors import SaveFormatError
from subscripts.stableHash import stable_hash_code
from subscripts.statRecords import STAT_RECORD_DICTS

__all__ = ["CURRENT_PAYLOAD", "STAT_LENGTH", "legacy_durability_raw", "upgrade_save", "upgrade_root"]

CURRENT_PAYLOAD = (34, 110, 2)
STAT_LENGTH = 205  # PlayerStatType.Count, the length the game writes every record at
STAT_RECORDS = 10
ENEMY_GROUPS = 5
BIOME_NAMES = {0: "None", 1: "Meadows", 2: "Swamp", 4: "Mountain", 8: "BlackForest", 16: "Plains",
               32: "AshLands", 64: "DeepNorth", 256: "Ocean", 512: "Mistlands", 639: "Land", 895: "All"}
LEGACY_RECORD_KEYS = ("known_worlds", "known_world_keys", "known_commands", "item_pickup_stats", "item_craft_stats")


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def legacy_durability_raw(durability: float) -> int:
    """``conv.i4(m_durability * 100f)``, when every precision the runtime may use gives the same integer."""
    try:
        exact = _f32(durability) * 100.0  # a float32 times 100 is exact in double, so wider precisions agree
        rounded = _f32(exact)
    except OverflowError:
        raise SaveFormatError(f"An item durability of {durability} is outside what the save upgrade can convert.") from None
    if not (math.isfinite(rounded) and -2**31 <= math.trunc(rounded) < 2**31):
        raise SaveFormatError(f"An item durability of {durability} is outside what the save upgrade can convert.")
    if math.trunc(rounded) != math.trunc(exact):
        raise SaveFormatError(f"An item durability of {durability} converts differently at different float "
                              "precisions; the save upgrade does not guess which one Valheim uses.")
    return int(math.trunc(exact))


def _fit_stats(stats: list) -> list:
    if len(stats) > STAT_LENGTH:
        raise SaveFormatError(f"The character records {len(stats)} statistics; the save upgrade converts at most "
                              f"the {STAT_LENGTH} Valheim records.")
    return list(stats) + [0.0] * (STAT_LENGTH - len(stats))


def _empty_record() -> dict:
    record = {name: {} for name in STAT_RECORD_DICTS}
    record["stats"] = [0.0] * STAT_LENGTH
    record["enemy_stats"] = [{} for _ in range(ENEMY_GROUPS)]
    return record


def _upgrade_container(root: dict) -> None:
    if root["version"] >= 46:
        for record in root["stat_records"]:
            record["stats"] = _fit_stats(record["stats"])
    else:
        record = _empty_record()
        record["stats"] = _fit_stats(root.pop("stats"))
        for key in LEGACY_RECORD_KEYS:
            record[key] = root.pop(key, None) or {}
        record["enemy_stats"][0] = root.pop("enemy_stats", None) or {}
        root["stat_records"] = [record] + [_empty_record() for _ in range(STAT_RECORDS - 1)]
    root["stat_length"] = STAT_LENGTH
    root["version"] = CURRENT_CHARACTER_SAVE_VERSION


def _biome_token(value) -> str:
    if isinstance(value, str):
        return value
    if value not in BIOME_NAMES:
        raise SaveFormatError(f"Known biome {value} is not a named Valheim biome; the save upgrade does not convert it.")
    return "$biome_" + BIOME_NAMES[value].lower()


def _upgrade_biomes(values) -> list:
    tokens = []
    for token in map(_biome_token, values or ()):
        if token not in tokens:
            tokens.append(token)
    return tokens


def _game_fields(item: dict, durability_raw: int, prefab_hash: int, has_prefab: bool) -> dict:
    """The item's values as the game holds them after loading it, in ``itemRecordTable``'s field names."""
    return {"durability_raw": durability_raw, "grid_x": item["grid_x"], "grid_y": item["grid_y"],
            "world_level": item["world_level"], "picked_up": item["picked_up"], "equipped": item["equipped"],
            "quality": item["quality"], "stack": item["stack"], "variant": item["variant"],
            "crafter_id": item["crafter_id"], "crafter_name": item["crafter_name"],
            "has_prefab": has_prefab, "prefab_hash": prefab_hash,
            "custom_data": item["custom_data"], "cheated": False}


def _as_the_game_writes(fields: dict) -> dict:
    """The record ``ItemData::Save`` writes for these values, as the item codec holds it; refused otherwise."""
    record = encode(fields)
    try:
        pkg = BinaryReader(record)
        item = read_item(pkg, CURRENT_PAYLOAD[1])
        pkg.require_exhausted("item record")
        out = BinaryWriter()
        write_item(out, item, CURRENT_PAYLOAD[1])
    except (SaveFormatError, ValueError, struct.error) as exc:
        raise SaveFormatError(f"An item cannot be held as Valheim {CURRENT_FORMAT_GAME_VERSION} writes it ({exc}).") from None
    if out.get_bytes() != record:
        raise SaveFormatError(f"An item cannot be held as Valheim {CURRENT_FORMAT_GAME_VERSION} writes it.")
    return item


def _legacy_item(item: dict) -> dict:
    # the game resolved the prefab (an empty name is skipped before this), so m_dropPrefab is set
    return _as_the_game_writes(_game_fields(item, legacy_durability_raw(item["durability"]),
                                            stable_hash_code(item["prefab"]), True))


def _item_109(item: dict) -> dict:
    wire = item["_wire"]
    # a 1.0 record stores the prefab only as a hash; a hash of 0 reads the same as no prefab
    return _as_the_game_writes(_game_fields(item, wire["durability_raw"], wire["prefab_hash"], wire["prefab_hash"] != 0))


def _upgrade_items(inventory: list, inventory_version: int):
    """The converted inventory and how many cheat bits the conversion cleared."""
    if inventory_version < 109:
        return [_legacy_item(item) for item in inventory if item.get("prefab")], 0
    if inventory_version > 109:
        return inventory, 0
    cleared = sum(1 for item in inventory if item["_wire"]["cheat_flags"] & CHEATED_BIT)
    return [_item_109(item) for item in inventory], cleared


def _upgrade_payload(payload: dict) -> int:
    payload["inventory"], cleared = _upgrade_items(payload["inventory"], payload["inventory_version"])
    if payload["version"] < 33:
        payload["known_biomes"] = _upgrade_biomes(payload.get("known_biomes"))
        payload["build_ui"] = b""
    payload.setdefault("pseudo_counter", [])
    payload.setdefault("item_upgrade_seeds", [])
    payload["version"], payload["inventory_version"], payload["skill_version"] = CURRENT_PAYLOAD
    return cleared


def upgrade_save(root: dict, payload: dict):
    """``(root, payload)`` at the current format; the inputs themselves when there is nothing to do.

    Nothing is upgraded that the editor cannot already write exactly: a current container, an
    unreadable container version and an unsupported payload triple come back unchanged.
    """
    version = root.get("version")
    triple = (payload.get("version"), payload.get("inventory_version"), payload.get("skill_version"))
    if version not in READABLE_CHARACTER_SAVE_VERSIONS or not payload_is_supported(payload):
        return root, payload
    if version == CURRENT_CHARACTER_SAVE_VERSION and triple == CURRENT_PAYLOAD:
        return root, payload
    root, payload = copy.deepcopy(root), copy.deepcopy(payload)
    source = {"from_container": version, "from_payload": list(triple)}
    _upgrade_container(root)
    source["cleared_cheat_flags"] = _upgrade_payload(payload)
    root["player_data_hex"] = pack_player_data_hex(payload)
    payload["_upgrade"] = source
    return root, payload


def upgrade_root(root: dict) -> dict:
    """The container alone, upgraded: for a character the editor builds itself."""
    return upgrade_save(root, unpack_player_data_hex(root["player_data_hex"]))[0]
