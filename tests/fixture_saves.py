"""Realistic character-save fixture shared by codec, tab, and main-window tests.

The fixture deliberately contains data the editor cannot represent in its
widgets: a modded skill ID, a modded hairstyle, a third model index, four active
foods, custom data, an off-grid inventory item, and a non-ASCII character name.
A no-op Save Changes must leave every one of these untouched.
"""
from pathlib import Path

from subscripts.fchUtil import serialize_save
from subscripts.playerDataUtil import pack_player_data_hex


def realistic_player_data() -> dict:
    return {
        "version": 29,
        "max_health": 10.0,
        "health": 9.5,
        "max_stamina": 20.0,
        "time_since_death": 1234.5,
        "guardian_power": "GP_Eikthyr",
        "guardian_power_cooldown": 42.0,
        "inventory_version": 106,
        "inventory": [
            {
                "prefab": "SwordBronze", "stack": 1, "durability": 88.0,
                "grid_x": 0, "grid_y": 0, "equipped": True, "quality": 2, "variant": 0,
                "crafter_id": 76561198000000000, "crafter_name": "Frostwulf",
                "custom_data": {"EpicLoot": "{\"rarity\":\"Epic\"}"},
                "world_level": 0, "picked_up": True,
            },
            {
                "prefab": "Wood", "stack": 50, "durability": 100.0,
                "grid_x": 3, "grid_y": 1, "equipped": False, "quality": 1, "variant": 0,
                "crafter_id": 0, "crafter_name": "", "custom_data": {},
                "world_level": 0, "picked_up": False,
            },
            {
                "prefab": "ModdedBackpackItem", "stack": 1, "durability": 100.0,
                "grid_x": 2, "grid_y": 7, "equipped": False, "quality": 1, "variant": 3,
                "crafter_id": 0, "crafter_name": "", "custom_data": {},
                "world_level": 1, "picked_up": True,
            },
        ],
        "known_recipes": ["Recipe_SwordBronze", "Recipe_Wood"],
        "known_stations": {"forge": 3, "piece_workbench": 5},
        "known_material": ["Wood", "Bronze"],
        "shown_tutorials": ["hammer"],
        "uniques": ["DragonEgg"],
        "trophies": ["TrophyBoar"],
        "known_biomes": [1, 2, 4],
        "known_texts": {"rune1": "text"},
        "beard": "Beard3",
        "hair": "HairModded99",
        "skin_color": [0.9, 0.8, 0.7],
        "hair_color": [0.3, 0.2, 0.1],
        "model_index": 2,
        "foods": [
            {"name": "CookedMeat", "time": 800.0},
            {"name": "Bread", "time": 1187.3456},
            {"name": "Sausages", "time": 950.0},
            {"name": "ModFood", "time": 100.0},
        ],
        "skill_version": 2,
        "skills": [
            {"id": 1, "level": 45.5157, "xp": 12.25},
            {"id": 500, "level": 30.0, "xp": 1.0},
        ],
        "custom_data": {"SomeMod.key": "value"},
        "stamina": 19.0,
        "max_eitr": 50.0,
        "eitr": 10.0,
    }


def realistic_player_hex() -> str:
    return pack_player_data_hex(realistic_player_data())


UNRESOLVED_HASH = -1891214396  # a 1.0 item the pinned catalogue cannot name


def realistic_v33_player_data() -> dict:
    """The version-29 fixture reshaped as Valheim 1.0 writes it: v33 payload, v109 items."""
    from subscripts.stableHash import stable_hash_code

    data = realistic_player_data()
    data["version"], data["inventory_version"] = 33, 109
    sword, wood, modded = data["inventory"]
    sword["_wire"] = {"prefab_hash": stable_hash_code("SwordBronze"), "durability_raw": 8800, "cheat_flags": 1}
    wood["_wire"] = {"prefab_hash": stable_hash_code("Wood"), "durability_raw": 10000, "cheat_flags": 0}
    modded["prefab"] = f"unknown#{UNRESOLVED_HASH}"
    modded["_wire"] = {"prefab_hash": UNRESOLVED_HASH, "durability_raw": 10000, "cheat_flags": 0}
    data["known_biomes"] = ["$biome_meadows", "Meadows", "$biome_none"]
    data["uniques"] = ["DragonEgg", "invrows 4"]
    data["build_ui"] = bytes(range(74))
    return data


def realistic_v33_player_hex() -> str:
    return pack_player_data_hex(realistic_v33_player_data())


def realistic_root_save(player_hex: str | None = None, name: str = "Frostwülf") -> dict:
    return {
        "version": 43,
        "stats": [1.0, 2.0, 3.5],
        "first_spawn": False,
        "worlds": [
            {
                "world_id": 123456789012,
                "have_custom_spawn": True, "spawn_point": [1.0, 2.0, 3.0],
                "have_logout_point": True, "logout_point": [4.0, 5.0, 6.0],
                "have_death_point": False, "death_point": [0.0, 0.0, 0.0],
                "home_point": [7.0, 8.0, 9.0],
                "map_data_hex": (b"\x01\x02\x03" * 1000).hex(),
            }
        ],
        "character_name": name,
        "player_id": 987654321,
        "start_seed": "abc123",
        "used_cheats": False,
        "date_created_unix": 1700000000,
        "known_worlds": {"WorldA": 1.5},
        "known_world_keys": {"defeated_eikthyr": 1.0},
        "known_commands": {"god": 1.0},
        "enemy_stats": {"Boar": 12.0},
        "item_pickup_stats": {"Wood": 300.0},
        "item_craft_stats": {"SwordBronze": 1.0},
        "player_data_hex": realistic_player_hex() if player_hex is None else player_hex,
    }


def write_fch(path, root_save: dict) -> Path:
    path = Path(path)
    path.write_bytes(serialize_save(root_save))
    return path


def _stat_record(populated: bool) -> dict:
    """One PlayerStats record. Only record 0 is populated in a real 1.0 save."""
    empty: dict = {}
    return {
        "stats": [1.0, 2.0, 3.5] if populated else [0.0, 0.0, 0.0],
        "known_worlds": {"WorldA": 1.5} if populated else empty,
        "known_world_keys": {"defeated_eikthyr": 1.0} if populated else empty,
        "known_commands": {"god": 1.0} if populated else empty,
        "enemy_stats": [{"$enemy_boar": 12.0}] if populated else [],
        "item_pickup_stats": {"$item_wood": 300.0} if populated else empty,
        "item_craft_stats": {"$item_swordbronze": 1.0} if populated else empty,
        "pickable_stats": {"Raspberry": 4.0} if populated else empty,
        "food_eaten_stats": empty,
        "pieces_placed_stats": empty,
    }


def realistic_v46_root_save(player_hex: str | None = None, name: str = "Frostwülf") -> dict:
    """A Valheim 1.0 container: ten stat records, only the first populated."""
    base = realistic_root_save(player_hex=player_hex, name=name)
    for key in ("stats", "known_worlds", "known_world_keys", "known_commands",
                "enemy_stats", "item_pickup_stats", "item_craft_stats"):
        base.pop(key)
    base["version"] = 46
    base["stat_length"] = 3
    base["stat_records"] = [_stat_record(index == 0) for index in range(10)]
    return base
