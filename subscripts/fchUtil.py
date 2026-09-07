"""Outer Valheim ``.fch`` container codec.

``parse_save`` and ``serialize_save`` are exact inverses for every supported
save: ``serialize_save(parse_save(data)) == data``. Strings are decoded with
``surrogateescape`` so bytes that are not valid UTF-8 survive a round trip, and
the reader refuses to return a save that still has unconsumed bytes.
"""
import hashlib
import json
import logging
import os
import sys

from subscripts.binaryIO import STRING_ERRORS, BinaryReader, BinaryWriter
from subscripts.saveErrors import SaveFormatError

logger = logging.getLogger(__name__)

__all__ = ["BinaryReader", "BinaryWriter", "STRING_ERRORS", "MIN_CHARACTER_SAVE_VERSION", "CURRENT_CHARACTER_SAVE_VERSION",
           "parse_save", "serialize_save", "decompile_fch", "compile_fch", "write_fch_bytes"]
USAGE = (
    "Valheim Save File Utility v{version}\n"
    "Usage:\n"
    "  Decompile: python fchUtil.py unpack <character.fch> <output.json>\n"
    "  Compile:   python fchUtil.py pack <input.json> <output.fch>"
)

# Real saves from version 40 onward round-trip byte-identical through this codec.
# Older layouts differ in fields this module does not gate on, so they are refused.
MIN_CHARACTER_SAVE_VERSION = 40
CURRENT_CHARACTER_SAVE_VERSION = 43


# ---------------------------------------------------------------- parsing

def _read_world(pkg: BinaryReader, version: int) -> dict:
    world = {"world_id": pkg.read_long()}
    world["have_custom_spawn"] = pkg.read_bool()
    world["spawn_point"] = pkg.read_vector3()
    world["have_logout_point"] = pkg.read_bool()
    world["logout_point"] = pkg.read_vector3()
    if version >= 30:
        world["have_death_point"] = pkg.read_bool()
        world["death_point"] = pkg.read_vector3()
    world["home_point"] = pkg.read_vector3()
    world["map_data_hex"] = pkg.read_byte_array().hex() if pkg.read_bool() else None
    return world


def _read_zpackage(pkg: BinaryReader) -> dict:
    version = pkg.read_int32()
    if version < MIN_CHARACTER_SAVE_VERSION:
        raise SaveFormatError(
            f"Character save version {version} is older than the minimum {MIN_CHARACTER_SAVE_VERSION} "
            "this build can read exactly."
        )
    save_data = {"version": version}
    save_data["stats"] = [pkg.read_float() for _ in range(pkg.read_int32())]
    save_data["first_spawn"] = pkg.read_bool()
    save_data["worlds"] = [_read_world(pkg, version) for _ in range(pkg.read_int32())]
    save_data["character_name"] = pkg.read_string()
    save_data["player_id"] = pkg.read_long()
    save_data["start_seed"] = pkg.read_string()
    save_data["used_cheats"] = pkg.read_bool()
    save_data["date_created_unix"] = pkg.read_long()
    save_data["known_worlds"] = pkg.read_float_dict()
    save_data["known_world_keys"] = pkg.read_float_dict()
    save_data["known_commands"] = pkg.read_float_dict()
    if version >= 42:
        save_data["enemy_stats"] = pkg.read_float_dict()
        save_data["item_pickup_stats"] = pkg.read_float_dict()
        save_data["item_craft_stats"] = pkg.read_float_dict()
    save_data["player_data_hex"] = pkg.read_byte_array().hex() if pkg.read_bool() else None
    pkg.require_exhausted("character container")
    return save_data


def parse_save(data: bytes) -> dict:
    """Parse a complete ``.fch`` file image into the save dictionary.

    The SHA-512 trailer is compared and logged here; strict rejection of a bad
    checksum belongs to ``subscripts.saveSafety`` which verifies before parsing.
    """
    file_reader = BinaryReader(data)
    zpackage_bytes = file_reader.read_byte_array()
    stored_hash = file_reader.read_byte_array()
    file_reader.require_exhausted("save envelope")
    if hashlib.sha512(zpackage_bytes).digest() != stored_hash:
        logger.warning("SHA-512 checksum mismatch; parsing the save anyway.")
    return _read_zpackage(BinaryReader(zpackage_bytes))


def decompile_fch(fch_path: str) -> dict:
    logger.info("Reading binary save: %s", fch_path)
    with open(fch_path, "rb") as f:
        return parse_save(f.read())


# ---------------------------------------------------------- serialization

def _write_world(pkg: BinaryWriter, world: dict, version: int) -> None:
    pkg.write_long(world["world_id"])
    pkg.write_bool(world["have_custom_spawn"])
    pkg.write_vector3(world["spawn_point"])
    pkg.write_bool(world["have_logout_point"])
    pkg.write_vector3(world["logout_point"])
    if version >= 30:
        pkg.write_bool(world["have_death_point"])
        pkg.write_vector3(world["death_point"])
    pkg.write_vector3(world["home_point"])
    map_data_hex = world["map_data_hex"]
    pkg.write_bool(map_data_hex is not None)
    if map_data_hex is not None:
        pkg.write_byte_array(bytes.fromhex(map_data_hex))


def _write_zpackage(save_data: dict) -> bytes:
    pkg = BinaryWriter()
    version = save_data["version"]
    pkg.write_int32(version)
    pkg.write_int32(len(save_data["stats"]))
    for stat in save_data["stats"]:
        pkg.write_float(stat)
    pkg.write_bool(save_data["first_spawn"])
    pkg.write_int32(len(save_data["worlds"]))
    for world in save_data["worlds"]:
        _write_world(pkg, world, version)
    pkg.write_string(save_data["character_name"])
    pkg.write_long(save_data["player_id"])
    pkg.write_string(save_data["start_seed"])
    pkg.write_bool(save_data["used_cheats"])
    pkg.write_long(save_data["date_created_unix"])
    pkg.write_float_dict(save_data["known_worlds"])
    pkg.write_float_dict(save_data["known_world_keys"])
    pkg.write_float_dict(save_data["known_commands"])
    if version >= 42:
        pkg.write_float_dict(save_data["enemy_stats"])
        pkg.write_float_dict(save_data["item_pickup_stats"])
        pkg.write_float_dict(save_data["item_craft_stats"])
    player_data_hex = save_data["player_data_hex"]
    pkg.write_bool(player_data_hex is not None)
    if player_data_hex is not None:
        pkg.write_byte_array(bytes.fromhex(player_data_hex))
    return pkg.get_bytes()


def serialize_save(save_data: dict) -> bytes:
    """Serialize the save dictionary into a complete ``.fch`` file image with its SHA-512 trailer."""
    zpackage_bytes = _write_zpackage(save_data)
    file_writer = BinaryWriter()
    file_writer.write_byte_array(zpackage_bytes)
    file_writer.write_byte_array(hashlib.sha512(zpackage_bytes).digest())
    return file_writer.get_bytes()


def write_fch_bytes(data: bytes, fch_path: str) -> None:
    """Write a file image and flush it to stable storage before returning."""
    with open(fch_path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def compile_fch(json_path: str, fch_path: str):
    logger.info("Reading JSON file: %s", json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        save_data = json.load(f)
    write_fch_bytes(serialize_save(save_data), fch_path)
    logger.info("Compiled and hashed save written to %s", fch_path)


# ------------------------------------------------------------------- CLI

def _main(argv: list) -> int:
    if len(argv) < 4:
        print(USAGE.format(version=CURRENT_CHARACTER_SAVE_VERSION))
        return 1
    mode, source_file, target_file = argv[1].lower(), argv[2], argv[3]
    if mode == "unpack":
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(decompile_fch(source_file), f, indent=2, ensure_ascii=True)
        return 0
    if mode == "pack":
        compile_fch(source_file, target_file)
        return 0
    logger.error("Unknown mode '%s'. Use 'unpack' or 'pack'.", mode)
    return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(_main(sys.argv))
