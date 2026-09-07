"""Create a brand-new character file from calibrated in-game defaults.

Defaults were taken verbatim from two characters created in Valheim on
2026-09-06 with no edits (see tests/test_new_character.py). No game binary is
embedded; the file is synthesised through the same codec that round-trips
real saves byte-identical.
"""
import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from subscripts.fchUtil import serialize_save, write_fch_bytes
from subscripts.playerDataUtil import pack_player_data_hex
from subscripts.saveSafety import verify_fch_round_trip

NAME_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]| (?=[A-Za-z0-9])){1,13}[A-Za-z0-9]$")
_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
STAT_SLOTS = 105
DEFAULT_SKIN = [0.65, 0.65, 0.65]
DEFAULT_HAIR_COLOR = [0.55, 0.39027130603790283, 0.270955890417099]
STARTING_INVENTORY = (
    {"prefab": "Torch", "durability": 20.0, "grid_x": 0, "grid_y": 0, "equipped": False},
    {"prefab": "ArmorRagsChest", "durability": 200.0, "grid_x": 0, "grid_y": 3, "equipped": True},
)


@dataclass
class NewCharacterSpec:
    name: str
    directory: str
    model_index: int = 0
    hair: str = ""
    beard: str = ""
    skin_color: List[float] = field(default_factory=lambda: list(DEFAULT_SKIN))
    hair_color: List[float] = field(default_factory=lambda: list(DEFAULT_HAIR_COLOR))

logger = logging.getLogger(__name__)


def validate_name(name: str) -> Optional[str]:
    """Return an error message, or None when the name is acceptable."""
    if not NAME_PATTERN.match(name or ""):
        return "Use 3 to 15 letters or digits, with single spaces between words."
    if name.lower() in _RESERVED:
        return "That name is reserved by Windows and cannot be a file name."
    return None


def _starting_item(spec: dict) -> dict:
    return {
        "prefab": spec["prefab"], "stack": 1, "durability": spec["durability"],
        "grid_x": spec["grid_x"], "grid_y": spec["grid_y"], "equipped": spec["equipped"],
        "quality": 1, "variant": 0, "crafter_id": 0, "crafter_name": "", "custom_data": {},
        "world_level": 0, "picked_up": False,
    }


def _default_payload(model_index, hair, beard, skin_color, hair_color) -> dict:
    return {
        "version": 29, "max_health": 100.0, "health": 100.0, "max_stamina": 100.0,
        "time_since_death": 999999.0, "guardian_power": "", "guardian_power_cooldown": 0.0,
        "inventory_version": 106, "inventory": [_starting_item(item) for item in STARTING_INVENTORY],
        "known_recipes": [], "known_stations": {}, "known_material": [], "shown_tutorials": [],
        "uniques": [], "trophies": [], "known_biomes": [], "known_texts": {},
        "beard": beard, "hair": hair, "skin_color": list(skin_color), "hair_color": list(hair_color),
        "model_index": int(model_index), "foods": [], "skill_version": 2, "skills": [],
        "custom_data": {}, "stamina": 100.0, "max_eitr": 0.0, "eitr": 0.0,
    }


def new_character_root(name: str, *, model_index: int = 0, hair: str = "", beard: str = "",
                       skin_color=None, hair_color=None, now: Optional[int] = None, rng=None) -> dict:
    """The outer save dictionary for a fresh character, ready for ``serialize_save``."""
    rng = rng or random.SystemRandom()
    player_id = rng.randint(-2**31, 2**31 - 1) or 1
    payload = _default_payload(model_index, hair, beard, skin_color or DEFAULT_SKIN, hair_color or DEFAULT_HAIR_COLOR)
    return {
        "version": 43, "stats": [0.0] * STAT_SLOTS, "first_spawn": True, "worlds": [],
        "character_name": name, "player_id": player_id, "start_seed": "", "used_cheats": False,
        "date_created_unix": int(time.time()) if now is None else int(now),
        "known_worlds": {}, "known_world_keys": {}, "known_commands": {},
        "enemy_stats": {}, "item_pickup_stats": {}, "item_craft_stats": {},
        "player_data_hex": pack_player_data_hex(payload),
    }


def root_from_spec(spec: NewCharacterSpec) -> dict:
    return new_character_root(spec.name, model_index=spec.model_index, hair=spec.hair, beard=spec.beard,
                              skin_color=spec.skin_color, hair_color=spec.hair_color)


def character_file_path(directory, name: str) -> Path:
    """The game names files after the lowercased character name."""
    return Path(directory) / f"{name.lower()}.fch"


def create_character_file(directory, root: dict) -> Path:
    """Write, verify, then place the new character; never overwrite an existing file."""
    directory = Path(directory)
    target = character_file_path(directory, root["character_name"])
    if target.exists():
        raise FileExistsError(f"A character file already exists at {target}")
    directory.mkdir(parents=True, exist_ok=True)
    temp_path = directory / f".wulfpack-forge-new-{target.stem}.tmp"
    try:
        write_fch_bytes(serialize_save(root), str(temp_path))
        verify_fch_round_trip(str(temp_path), root)
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except OSError as exc:
                logger.warning("Could not remove temporary file %s: %s", temp_path, exc)
    return target
