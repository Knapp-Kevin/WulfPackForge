"""The player-statistics block introduced by character save version 46 (Valheim 1.0).

Version 43 stored one flat set of statistics in the container tail. Version 46 stores an
array of ten ``PlayerStats`` records ahead of ``first_spawn``, each holding a float array
and nine collections. Only the first record is populated in practice, but all ten are
read and written positionally because the game writes them unconditionally.

``m_enemyStats`` is the one collection the game nests: it is a list of ``string -> float``
dictionaries rather than a single dictionary. The other eight are flat.

Field order is taken from ``PlayerProfile::SavePlayerToDisk`` in the game's own assembly;
see docs/research-brief-valheim-1.0-save-format-2026-09-09.md.
"""
from subscripts.binaryIO import BinaryReader, BinaryWriter

__all__ = ["STAT_RECORD_DICTS", "read_stat_records", "write_stat_records"]

# The eight flat collections, in the order the game writes them. ``enemy_stats`` is
# absent because it nests; it is written between ``known_commands`` and
# ``item_pickup_stats`` by the reader and writer below.
STAT_RECORD_DICTS = (
    "known_worlds",
    "known_world_keys",
    "known_commands",
    "item_pickup_stats",
    "item_craft_stats",
    "pickable_stats",
    "food_eaten_stats",
    "pieces_placed_stats",
)


def _read_record(pkg: BinaryReader, stat_length: int) -> dict:
    record = {"stats": [pkg.read_float() for _ in range(stat_length)]}
    for name in STAT_RECORD_DICTS[:3]:
        record[name] = pkg.read_float_dict()
    record["enemy_stats"] = [pkg.read_float_dict() for _ in range(pkg.read_int32())]
    for name in STAT_RECORD_DICTS[3:]:
        record[name] = pkg.read_float_dict()
    return record


def read_stat_records(pkg: BinaryReader, count: int, stat_length: int) -> list:
    """Read ``count`` statistics records, each carrying ``stat_length`` floats."""
    return [_read_record(pkg, stat_length) for _ in range(count)]


def _write_record(pkg: BinaryWriter, record: dict) -> None:
    for stat in record["stats"]:
        pkg.write_float(stat)
    for name in STAT_RECORD_DICTS[:3]:
        pkg.write_float_dict(record[name])
    pkg.write_int32(len(record["enemy_stats"]))
    for group in record["enemy_stats"]:
        pkg.write_float_dict(group)
    for name in STAT_RECORD_DICTS[3:]:
        pkg.write_float_dict(record[name])


def write_stat_records(pkg: BinaryWriter, records: list) -> None:
    """Write every statistics record in order; the count is written by the caller."""
    for record in records:
        _write_record(pkg, record)
