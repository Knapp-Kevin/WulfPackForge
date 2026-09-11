"""The game-install catalogue generator, on synthetic input: record shape, filtering, document, cross-check."""
import unittest

from tools.catalogFromGame import (
    ITEM_TYPES, build_document, cross_check, english_names, item_record, merge_asset_ids,
)

ENGLISH = {"item_sword_gold_frostfire": "Frostfire Sword", "item_wood": "Wood"}


def shared(**overrides):
    base = {
        "m_name": "$item_sword_gold_frostfire", "m_itemType": 3, "m_maxStackSize": 1, "m_maxQuality": 4,
        "m_variants": 0, "m_useDurability": 1, "m_maxDurability": 400.0, "m_durabilityPerLevel": 50.0,
        "m_icons": [{"m_FileID": 6, "m_PathID": 1}],
        "m_damages": {"m_damage": 0.0, "m_blunt": 0.0, "m_slash": 138.0, "m_pierce": 0.0, "m_chop": 0.0,
                      "m_pickaxe": 0.0, "m_fire": 12.0, "m_frost": 88.0, "m_lightning": 0.0, "m_poison": 0.0,
                      "m_spirit": 0.0, "m_nonPlayer": 500.0},
        "m_damagesPerLevel": {"m_slash": 10.0, "m_fire": 3.0, "m_frost": 3.0, "m_nonPlayer": 9.0},
    }
    base.update(overrides)
    return base


def records(count, selectable=True):
    return [{"prefab": f"Item{i}", "display_name": f"Item {i}", "item_type": "Material", "asset_id": None,
             "selectable": selectable, "limits": {"max_stack": 1, "max_quality": 1, "variants": 0}} for i in range(count)]


class RecordTests(unittest.TestCase):
    def test_english_names_reads_the_second_column(self):
        csv = ('﻿?,English,Swedish\nitem_sword_gold_frostfire,Frostfire Sword,,Lance\n'
               'item_sword_gold_frostfire_description,"Flames dance, but are they hot?",,x\n')
        names = english_names(csv)
        self.assertEqual(names["item_sword_gold_frostfire"], "Frostfire Sword")
        self.assertEqual(names["item_sword_gold_frostfire_description"], "Flames dance, but are they hot?")

    def test_item_record_maps_every_shared_field(self):
        record = item_record("SwordGold_FrostFire", shared(), ENGLISH)
        self.assertEqual((record["display_name"], record["item_type"], record["selectable"]), ("Frostfire Sword", "OneHandedWeapon", True))
        self.assertEqual(record["limits"], {"max_stack": 1, "max_quality": 4, "variants": 0})
        self.assertEqual(record["durability"], {"max": 400.0, "per_level": 50.0})
        self.assertEqual(record["damage"]["base"], {"slash": 138.0, "fire": 12.0, "frost": 88.0})
        self.assertEqual(record["damage"]["per_level"], {"slash": 10.0, "fire": 3.0, "frost": 3.0})
        self.assertIsNone(record["asset_id"])

    def test_generic_damage_counts_and_non_player_damage_does_not(self):
        cheat = shared(m_name="$item_sledge_cheat", m_damages={"m_damage": 99999.0, "m_nonPlayer": 5.0}, m_damagesPerLevel={})
        record = item_record("SledgeCheat", cheat, {})
        self.assertEqual(record["damage"], {"base": {"damage": 99999.0}, "per_level": {}})
        self.assertEqual(record["display_name"], "Sledge Cheat", "a token with no English row humanises the prefab")

    def test_item_record_drops_duplicates_and_non_items(self):
        self.assertIsNone(item_record("BoneFragments (1)", shared(m_name="$item_bonefragments"), {}))
        self.assertIsNone(item_record("Greydwarf_shaman_heal_frozen", shared(m_name="heal"), {}))
        self.assertIsNotNone(item_record("BoneFragments", shared(m_name="$item_bonefragments"), {}))
        attack = item_record("wraith_melee", shared(m_name="Wraith melee", m_icons=[]), {})
        self.assertEqual((attack["display_name"], attack["selectable"]), ("Wraith melee", False), "plain-named creature attacks stay, as in JotunnDoc")
        npc_copy = item_record("FW_AxeBronze", shared(m_name="$item_axe_bronze"), {"item_axe_bronze": "Bronze Axe"})
        self.assertEqual((npc_copy["display_name"], npc_copy["selectable"]), ("Bronze Axe", False), "NPC-held copies stay in the catalogue but out of the picker")

    def test_an_item_without_icons_or_durability_or_damage_records_none_of_them(self):
        record = item_record("Wood", shared(m_name="$item_wood", m_itemType=1, m_icons=[], m_useDurability=0,
                                            m_damages={}, m_damagesPerLevel={}), ENGLISH)
        self.assertFalse(record["selectable"])
        self.assertNotIn("durability", record)
        self.assertNotIn("damage", record)

    def test_item_type_table_is_the_game_enum(self):
        self.assertEqual(ITEM_TYPES[24], "Trinket")
        self.assertEqual(ITEM_TYPES[22], "TwoHandedWeaponLeft")
        self.assertEqual(ITEM_TYPES[21], "Fish")
        self.assertNotIn(8, ITEM_TYPES)
        self.assertEqual(len(ITEM_TYPES), 24)


class DocumentTests(unittest.TestCase):
    def test_build_document_refuses_a_suspiciously_small_catalogue(self):
        with self.assertRaisesRegex(RuntimeError, "suspiciously small"):
            build_document(records(20), "1.0.12", 1)
        document = build_document(records(300) + [None], "1.0.12", 25253764)
        self.assertEqual((document["schema_version"], document["game_version"], document["build_id"]), (2, "1.0.12", 25253764))
        self.assertEqual((document["item_count"], document["selectable_item_count"]), (300, 300))
        self.assertEqual(document["items"][0]["prefab"], "Item0")

    def test_cross_check_reports_set_type_and_selectable_differences_by_name(self):
        ours = {"items": records(3)}
        theirs = {"items": [dict(r) for r in records(3)]}
        self.assertEqual(cross_check(ours, theirs), [])
        theirs["items"][0]["item_type"] = "Consumable"
        theirs["items"][1]["selectable"] = False
        theirs["items"][2]["prefab"] = "Elsewhere"
        lines = cross_check(ours, theirs)
        self.assertEqual(len(lines), 4)
        self.assertTrue(any("only in the game data: Item2" in line for line in lines))
        self.assertTrue(any("only in JotunnDoc: Elsewhere" in line for line in lines))
        self.assertTrue(any(line.startswith("type differs for Item0") for line in lines))
        self.assertTrue(any(line.startswith("selectable differs for Item1") for line in lines))

    def test_merge_asset_ids_fills_only_matching_prefabs(self):
        ours = {"items": records(2)}
        merged = merge_asset_ids(ours, {"items": [{"prefab": "Item0", "asset_id": "abc"}, {"prefab": "Other", "asset_id": "zzz"}]})
        self.assertEqual([r["asset_id"] for r in merged["items"]], ["abc", None])


if __name__ == "__main__":
    unittest.main()
