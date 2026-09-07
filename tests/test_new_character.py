import copy
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from subscripts import newCharacter
from subscripts.fchUtil import parse_save, serialize_save
from subscripts.newCharacter import (
    create_character_file,
    character_file_path,
    new_character_root,
    validate_name,
)
from subscripts.playerDataUtil import unpack_player_data_hex
from subscripts.saveErrors import SaveFormatError
from subscripts.saveSafety import verify_fch_round_trip


# Verbatim from a character created in Valheim on 2026-09-06 with no edits
# ("Template"), except player_id and date_created_unix, which are asserted separately.
TEMPLATE_OUTER = {
    "version": 43,
    "stats": [0.0] * 105,
    "first_spawn": True,
    "worlds": [],
    "character_name": "Template",
    "start_seed": "",
    "used_cheats": False,
    "known_worlds": {},
    "known_world_keys": {},
    "known_commands": {},
    "enemy_stats": {},
    "item_pickup_stats": {},
    "item_craft_stats": {},
}

TEMPLATE_PAYLOAD = {
    "version": 29,
    "max_health": 100.0,
    "health": 100.0,
    "max_stamina": 100.0,
    "time_since_death": 999999.0,
    "guardian_power": "",
    "guardian_power_cooldown": 0.0,
    "inventory_version": 106,
    "inventory": [
        {"prefab": "Torch", "stack": 1, "durability": 20.0, "grid_x": 0, "grid_y": 0, "equipped": False,
         "quality": 1, "variant": 0, "crafter_id": 0, "crafter_name": "", "custom_data": {},
         "world_level": 0, "picked_up": False},
        {"prefab": "ArmorRagsChest", "stack": 1, "durability": 200.0, "grid_x": 0, "grid_y": 3, "equipped": True,
         "quality": 1, "variant": 0, "crafter_id": 0, "crafter_name": "", "custom_data": {},
         "world_level": 0, "picked_up": False},
    ],
    "known_recipes": [],
    "known_stations": {},
    "known_material": [],
    "shown_tutorials": [],
    "uniques": [],
    "trophies": [],
    "known_biomes": [],
    "known_texts": {},
    "beard": "",
    "hair": "",
    "skin_color": [0.6499999761581421, 0.6499999761581421, 0.6499999761581421],
    "hair_color": [0.550000011920929, 0.39027130603790283, 0.270955890417099],
    "model_index": 0,
    "foods": [],
    "skill_version": 2,
    "skills": [],
    "custom_data": {},
    "stamina": 100.0,
    "max_eitr": 0.0,
    "eitr": 0.0,
}

CORVUS_APPEARANCE = {
    "beard": "Beard3",
    "hair": "Hair7",
    "skin_color": [0.4431372582912445, 0.11372549086809158, 0.8196078538894653],
    "hair_color": [0.12156862765550613, 0.0313725508749485, 0.22745098173618317],
}


class NewCharacterRootTests(unittest.TestCase):
    def test_root_matches_in_game_template(self):
        root = new_character_root("Template", now=1788718254, rng=random.Random(7))
        parsed = parse_save(serialize_save(root))
        payload = unpack_player_data_hex(parsed.pop("player_data_hex"))
        player_id = parsed.pop("player_id")
        self.assertEqual(parsed.pop("date_created_unix"), 1788718254)
        self.assertEqual(parsed, TEMPLATE_OUTER)
        self.assertEqual(payload, TEMPLATE_PAYLOAD)
        self.assertNotEqual(player_id, 0)
        self.assertTrue(-2**31 <= player_id < 2**31)

    def test_appearance_choices_match_a_customised_in_game_character(self):
        root = new_character_root("Corvus", hair="Hair7", beard="Beard3",
                                  skin_color=CORVUS_APPEARANCE["skin_color"],
                                  hair_color=CORVUS_APPEARANCE["hair_color"])
        payload = unpack_player_data_hex(parse_save(serialize_save(root))["player_data_hex"])
        self.assertEqual({k: payload[k] for k in CORVUS_APPEARANCE}, CORVUS_APPEARANCE)
        self.assertEqual(root["character_name"], "Corvus")

    def test_two_characters_get_different_ids(self):
        a = new_character_root("One", rng=random.Random(1))
        b = new_character_root("Two", rng=random.Random(2))
        self.assertNotEqual(a["player_id"], b["player_id"])


class NameValidationTests(unittest.TestCase):
    def test_accepts_plain_and_spaced_names(self):
        self.assertIsNone(validate_name("Frostwulf"))
        self.assertIsNone(validate_name("Sigrun the Bold"))

    def test_rejects_short_long_reserved_and_symbols(self):
        for bad in ("ab", "Sixteencharacters", "Con", "Bad*Name", "", " Lead", "double  space"):
            self.assertIsNotNone(validate_name(bad), bad)


class CharacterFileTests(unittest.TestCase):
    def test_creates_lowercased_file_that_verifies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = new_character_root("Template", now=1788718254, rng=random.Random(3))
            path = create_character_file(Path(temp_dir), root)
            self.assertEqual(path.name, "template.fch")
            self.assertEqual(character_file_path(Path(temp_dir), "Template"), path)
            self.assertEqual(verify_fch_round_trip(str(path)), root)
            self.assertEqual(sorted(p.name for p in Path(temp_dir).iterdir()), ["template.fch"])

    def test_refuses_to_overwrite_an_existing_character(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = create_character_file(Path(temp_dir), new_character_root("Template", rng=random.Random(1)))
            original = first.read_bytes()
            with self.assertRaises(FileExistsError):
                create_character_file(Path(temp_dir), new_character_root("template", rng=random.Random(2)))
            self.assertEqual(first.read_bytes(), original)

    def test_verification_failure_leaves_no_file_behind(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = new_character_root("Template", rng=random.Random(1))
            with patch.object(newCharacter, "verify_fch_round_trip", side_effect=SaveFormatError("boom")):
                with self.assertRaises(SaveFormatError):
                    create_character_file(Path(temp_dir), copy.deepcopy(root))
            self.assertEqual(list(Path(temp_dir).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
