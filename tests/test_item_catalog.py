import unittest

from data.items import (
    CATALOG_GAME_VERSION,
    CATALOG_ITEM_COUNT,
    CATALOG_SELECTABLE_ITEM_COUNT,
    completion_labels,
    resolve_item,
)


class ItemCatalogTests(unittest.TestCase):
    def test_catalog_is_pinned_to_valheim_1_0_12(self):
        from data.catalogDocument import catalog_document
        self.assertEqual(CATALOG_GAME_VERSION, "1.0.12")
        self.assertEqual(catalog_document()["build_id"], 25253764)
        self.assertGreaterEqual(CATALOG_ITEM_COUNT, 1500)
        self.assertGreaterEqual(CATALOG_SELECTABLE_ITEM_COUNT, 900)

    def test_every_curated_limit_equals_the_games_limit(self):
        from data.catalogDocument import record
        from data.items import CONSTRAINT_OVERRIDES
        checked = 0
        for key, limits in CONSTRAINT_OVERRIDES.items():
            entry = record(key)
            if entry is None:
                continue
            checked += 1
            game = entry["limits"]
            if limits.max_stack is not None:
                self.assertEqual(limits.max_stack, game["max_stack"], key)
            if limits.max_quality is not None:
                self.assertEqual(limits.max_quality, game["max_quality"], key)
        self.assertGreaterEqual(checked, 60)

    def test_frostfire_weapons_resolve_by_name(self):
        from subscripts.itemCodec import resolve_prefab_hash
        from subscripts.stableHash import stable_hash_code
        self.assertEqual(resolve_item("SpearGold_FrostFire").display_name, "Frostfire Spear")
        self.assertEqual(resolve_prefab_hash(stable_hash_code("SwordGold_FrostFire")), "SwordGold_FrostFire")

    def test_resolves_prefab_case_insensitively_and_keeps_curated_limits(self):
        item = resolve_item("arrowwood")
        self.assertIsNotNone(item)
        self.assertEqual(item.prefab, "ArrowWood")
        self.assertEqual(item.max_stack, 100)

    def test_resolves_unique_human_readable_name(self):
        item = resolve_item("Breastplate of Ask")
        self.assertIsNotNone(item)
        self.assertEqual(item.prefab, "ArmorAshlandsMediumChest")

    def test_ambiguous_human_readable_name_requires_prefab_disambiguation(self):
        self.assertIsNone(resolve_item("Arbalest"))  # CrossbowArbalest and the Dverger-held Arbalest share the name
        item = resolve_item("Arbalest — CrossbowArbalest")
        self.assertIsNotNone(item)
        self.assertEqual(item.prefab, "CrossbowArbalest")
        sword = resolve_item("Bronze Sword — SwordBronze")
        self.assertEqual((sword.prefab, sword.max_quality), ("SwordBronze", 4))

    def test_resolves_current_generated_item_metadata(self):
        item = resolve_item("Breastplate of Ask")
        self.assertIsNotNone(item)
        self.assertEqual(item.prefab, "ArmorAshlandsMediumChest")
        self.assertEqual(item.item_type, "Chest")
        self.assertTrue(item.asset_id)

    def test_resolves_completion_label(self):
        label = "Megingjord — BeltStrength"
        item = resolve_item(label)
        self.assertIsNotNone(item)
        self.assertEqual(item.prefab, "BeltStrength")

    def test_internal_objectdb_rows_do_not_pollute_player_completion_list(self):
        internal = resolve_item("Abomination_attack1")
        self.assertIsNotNone(internal)
        labels = completion_labels()
        self.assertFalse(any("Abomination_attack1" in label for label in labels))

    def test_unknown_or_modded_prefab_is_not_coerced(self):
        self.assertIsNone(resolve_item("MyModdedLegendaryHammer"))

    def test_completion_labels_are_search_friendly(self):
        labels = completion_labels()
        self.assertIn("Wood Arrow — ArrowWood", labels)
        self.assertIn("Bronze Sword — SwordBronze", labels)


if __name__ == "__main__":
    unittest.main()
