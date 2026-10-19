"""The save upgrade: a readable older character, converted as Valheim 1.0.20 converts it."""
import copy
import unittest

from subscripts.fchUtil import parse_save, serialize_save
from subscripts.playerDataUtil import pack_player_data_hex, unpack_player_data_hex
from subscripts.saveErrors import SaveFormatError
from subscripts.saveUpgrade import STAT_LENGTH, legacy_durability_raw, upgrade_root, upgrade_save
from subscripts.stableHash import stable_hash_code
from subscripts.statRecords import STAT_RECORD_DICTS
from tests.fixture_saves import (realistic_player_data, realistic_root_save, realistic_v33_player_data,
                                 realistic_v33_player_hex, realistic_v46_root_save, realistic_v47_root_save)


def upgrade(root):
    return upgrade_save(root, unpack_player_data_hex(root["player_data_hex"]))


def legacy_with(edit):
    payload = realistic_player_data()
    edit(payload)
    return realistic_root_save(pack_player_data_hex(payload))


class ContainerUpgradeTests(unittest.TestCase):
    def test_a_v43_container_becomes_ten_records(self):
        fixture = realistic_root_save()
        root, _payload = upgrade(fixture)
        self.assertEqual((root["version"], root["stat_length"], len(root["stat_records"])), (47, STAT_LENGTH, 10))
        first = root["stat_records"][0]
        self.assertEqual(first["stats"], fixture["stats"] + [0.0] * (STAT_LENGTH - len(fixture["stats"])))
        for key in ("known_worlds", "known_world_keys", "known_commands", "item_pickup_stats", "item_craft_stats"):
            self.assertEqual(first[key], fixture[key], key)
        self.assertEqual(first["enemy_stats"], [fixture["enemy_stats"], {}, {}, {}, {}])
        for record in root["stat_records"][1:]:
            self.assertEqual((record["stats"], record["enemy_stats"]), ([0.0] * STAT_LENGTH, [{}] * 5))
            self.assertTrue(all(record[key] == {} for key in STAT_RECORD_DICTS))
        legacy_keys = {"stats", "known_worlds", "known_world_keys", "known_commands", "enemy_stats",
                       "item_pickup_stats", "item_craft_stats"}
        self.assertFalse(legacy_keys & set(root))

    def test_a_v40_container_without_the_newer_dictionaries_gets_empty_ones(self):
        fixture = realistic_root_save()
        fixture["version"] = 40
        for key in ("enemy_stats", "item_pickup_stats", "item_craft_stats"):
            fixture.pop(key)
        first = upgrade(fixture)[0]["stat_records"][0]
        self.assertEqual((first["enemy_stats"][0], first["item_pickup_stats"], first["item_craft_stats"]), ({}, {}, {}))

    def test_a_v46_container_is_fitted_to_the_games_record_length(self):
        root = upgrade(realistic_v46_root_save(realistic_v33_player_hex()))[0]
        self.assertEqual(root["stat_length"], STAT_LENGTH)
        self.assertEqual(root["stat_records"][0]["stats"][:3], [1.0, 2.0, 3.5])
        self.assertTrue(all(len(record["stats"]) == STAT_LENGTH for record in root["stat_records"]))

    def test_a_statistics_array_longer_than_the_game_records_is_refused(self):
        fixture = realistic_root_save()
        fixture["stats"] = [0.0] * (STAT_LENGTH + 1)
        with self.assertRaises(SaveFormatError):
            upgrade(fixture)


class PayloadUpgradeTests(unittest.TestCase):
    def test_integer_biomes_become_the_games_tokens(self):
        root = legacy_with(lambda p: p.update(known_biomes=[1, 8, 0, 1, 64, 32, 639]))
        payload = upgrade(root)[1]
        self.assertEqual(payload["known_biomes"],
                         ["$biome_meadows", "$biome_blackforest", "$biome_none", "$biome_deepnorth",
                          "$biome_ashlands", "$biome_land"])
        self.assertEqual((payload["build_ui"], payload["pseudo_counter"], payload["item_upgrade_seeds"]), (b"", [], []))

    def test_a_biome_integer_that_is_not_a_named_value_is_refused(self):
        for value in (3, 1024):
            with self.subTest(value=value), self.assertRaises(SaveFormatError):
                upgrade(legacy_with(lambda p: p.update(known_biomes=[1, value])))

    def test_a_v33_payload_keeps_its_build_ui_blob(self):
        payload = upgrade(realistic_v46_root_save(realistic_v33_player_hex()))[1]
        self.assertEqual(payload["build_ui"], realistic_v33_player_data()["build_ui"])
        self.assertEqual(payload["known_biomes"], realistic_v33_player_data()["known_biomes"])


class ItemUpgradeTests(unittest.TestCase):
    def test_legacy_durability_is_truncated_as_the_game_truncates(self):
        self.assertEqual(legacy_durability_raw(696.4999389648438), 69649)
        self.assertEqual(legacy_durability_raw(1934.869384765625), 193486)
        root = legacy_with(lambda p: p["inventory"][0].update(durability=696.4999389648438))
        sword = unpack_player_data_hex(upgrade(root)[0]["player_data_hex"])["inventory"][0]
        self.assertEqual(sword["_wire"]["durability_raw"], 69649)

    def test_a_legacy_durability_outside_int32_is_refused(self):
        for value in (21474836.48, float("inf"), 1e37, 1e39):
            with self.subTest(value=value), self.assertRaises(SaveFormatError):
                legacy_durability_raw(value)

    def test_a_durability_whose_truncation_depends_on_float_precision_is_refused(self):
        # float32(0.29) * 100 is 28.99999916...: 29 when the product is rounded to float32, 28 when held exactly
        with self.assertRaises(SaveFormatError):
            legacy_durability_raw(0.29)
        self.assertEqual(legacy_durability_raw(0.5), 50)

    def test_a_legacy_item_becomes_a_hashed_record_with_no_cheat_state(self):
        legacy = realistic_player_data()["inventory"][0]
        written = unpack_player_data_hex(upgrade(realistic_root_save())[0]["player_data_hex"])["inventory"][0]
        self.assertEqual(written["_wire"]["prefab_hash"], stable_hash_code(legacy["prefab"]))
        self.assertEqual(written["_wire"]["cheat_flags"], 0)
        for key in ("prefab", "stack", "quality", "variant", "grid_x", "grid_y", "equipped", "crafter_id",
                    "crafter_name", "custom_data", "world_level", "picked_up"):
            self.assertEqual(written[key], legacy[key], key)

    def test_a_modded_legacy_item_is_kept_by_its_hash_and_named_as_the_reader_names_it(self):
        root = legacy_with(lambda p: p["inventory"][0].update(prefab="VAFireBolt"))
        upgraded_root, payload = upgrade(root)
        self.assertEqual(payload["inventory"][0]["_wire"]["prefab_hash"], stable_hash_code("VAFireBolt"))
        self.assertEqual(payload["inventory"][0]["prefab"], f"unknown#{stable_hash_code('VAFireBolt')}")
        reread = unpack_player_data_hex(upgraded_root["player_data_hex"])["inventory"][0]
        self.assertEqual(reread["prefab"], payload["inventory"][0]["prefab"])

    def test_an_empty_prefab_legacy_item_is_dropped(self):
        root = legacy_with(lambda p: p["inventory"][0].update(prefab=""))
        payload = upgrade(root)[1]
        kept = [(item["grid_x"], item["grid_y"]) for item in realistic_player_data()["inventory"][1:]]
        self.assertEqual([(item["grid_x"], item["grid_y"]) for item in payload["inventory"]], kept)

    def test_a_v109_cheat_byte_becomes_zero_and_its_bit_is_counted(self):
        data = realistic_v33_player_data()
        data["inventory"][0]["_wire"]["cheat_flags"] = 3
        data["inventory"][1]["_wire"]["cheat_flags"] = 2
        payload = upgrade(realistic_v46_root_save(pack_player_data_hex(data)))[1]
        self.assertEqual([item["_wire"]["cheat_flags"] for item in payload["inventory"]], [0, 0, 0])
        self.assertEqual(payload["_upgrade"]["cleared_cheat_flags"], 1)

    def test_a_v109_items_stored_durability_passes_through(self):
        # 146666 is frost's hood: a load and save in 1.0.20 rewrites it 146665, on every load at any
        # version (ItemData::Load, item.il 11ce33); the upgrade leaves that to the game
        data = realistic_v33_player_data()
        data["inventory"][0].update(durability=146666 / 100)
        data["inventory"][0]["_wire"]["durability_raw"] = 146666
        root = upgrade(realistic_v46_root_save(pack_player_data_hex(data)))[0]
        reparsed = unpack_player_data_hex(parse_save(serialize_save(root))["player_data_hex"])
        self.assertEqual(reparsed["inventory"][0]["_wire"]["durability_raw"], 146666)

    def test_a_legacy_item_is_written_as_the_game_writes_it(self):
        # crafter id 0 with a name: the game gates both crafter fields on the id (itemRecordTable, 11cc81)
        root = legacy_with(lambda p: p["inventory"][0].update(crafter_id=0, crafter_name="Hodr", grid_x=257))
        sword = unpack_player_data_hex(upgrade(root)[0]["player_data_hex"])["inventory"][0]
        self.assertEqual((sword["crafter_id"], sword["crafter_name"]), (0, ""))
        self.assertEqual(sword["grid_x"], 1)  # conv.u1 of 257, as ItemData::Save writes it

    def test_an_item_the_codec_cannot_hold_as_the_game_writes_it_is_refused(self):
        many = {f"k{i}": "v" for i in range(0x8000)}
        edits = (("quality", 65537), ("stack", 65537), ("custom_data", many))
        for key, value in edits:
            with self.subTest(key=key), self.assertRaises(SaveFormatError):
                upgrade(legacy_with(lambda p: p["inventory"][0].update({key: value})))

    def test_the_upgrade_records_what_it_did(self):
        record = upgrade(realistic_root_save())[1]["_upgrade"]
        self.assertEqual(record, {"from_container": 43, "from_payload": [29, 106, 2], "cleared_cheat_flags": 0})

    def test_upgraded_output_reparses_to_exhaustion_and_reserializes_identically(self):
        for fixture in (realistic_root_save(), realistic_v46_root_save(realistic_v33_player_hex())):
            with self.subTest(version=fixture["version"]):
                data = serialize_save(upgrade(fixture)[0])
                reparsed = parse_save(data)
                payload = unpack_player_data_hex(reparsed["player_data_hex"])
                self.assertEqual(serialize_save(reparsed), data)
                self.assertEqual((payload["version"], payload["inventory_version"], payload["skill_version"]), (34, 110, 2))

    def test_current_and_unsupported_inputs_are_returned_unchanged(self):
        current = realistic_v47_root_save()
        current_payload = unpack_player_data_hex(current["player_data_hex"])
        result = upgrade_save(current, current_payload)
        self.assertIs(result[0], current)
        self.assertIs(result[1], current_payload)
        odd = realistic_player_data()
        odd["version"] = 30
        root = realistic_root_save()
        result = upgrade_save(root, odd)
        self.assertIs(result[0], root)
        self.assertIs(result[1], odd)

    def test_a_current_container_with_an_older_payload_has_its_payload_upgraded(self):
        older_inside = realistic_v47_root_save(realistic_v33_player_hex())
        root, payload = upgrade(older_inside)
        self.assertEqual((root["version"], payload["version"], payload["inventory_version"]), (47, 34, 110))
        self.assertEqual(payload["_upgrade"]["from_container"], 47)
        self.assertEqual(payload["_upgrade"]["cleared_cheat_flags"], 1)

    def test_inputs_are_not_mutated(self):
        root = realistic_root_save()
        payload = unpack_player_data_hex(root["player_data_hex"])
        before = copy.deepcopy(root), copy.deepcopy(payload)
        upgrade_save(root, payload)
        self.assertEqual((root, payload), before)

    def test_upgrade_root_is_the_container_of_upgrade_save(self):
        self.assertEqual(upgrade_root(realistic_root_save()), upgrade(realistic_root_save())[0])


if __name__ == "__main__":
    unittest.main()
