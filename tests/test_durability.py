import os
import unittest
from tests.qt_support import QtTestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from data.durability import default_durability, durability_entry, max_durability
from ui.itemEditDialog import ItemEditDialog


APP = QApplication.instance() or QApplication([])


def item_data(prefab, durability=100.0, quality=1):
    return {"prefab": prefab, "stack": 1, "durability": durability, "quality": quality, "variant": 0, "equipped": False}


class MaxDurabilityTests(QtTestCase):
    def test_maximum_follows_base_and_per_level_from_the_catalogue(self):
        self.assertEqual(max_durability("SwordGold_FrostFire", 1), 400.0)
        self.assertEqual(max_durability("SwordGold_FrostFire", 4), 550.0)
        self.assertIsNone(max_durability("NotARealPrefab", 1))

    def test_shipped_table_arithmetic(self):
        self.assertEqual(max_durability("SpearSplitner", 1), 300.0)
        self.assertEqual(max_durability("SpearSplitner", 3), 400.0)
        self.assertIsNone(max_durability("Tankard", 1))
        self.assertIsNone(max_durability("NotARealPrefab", 1))
        self.assertIsNotNone(durability_entry("ArmorWolfChest"))

    def test_ashlands_bow_maximum_is_the_games_value(self):
        self.assertEqual(max_durability("BowAshlands", 1), 300.0)

    def test_an_item_that_never_wears_has_no_maximum(self):
        entry = {"base": 0.0, "per_level": 0.0}
        self.assertIsNone(max_durability("x", 1, entry=entry))
        self.assertIsNone(max_durability("HelmetMidsummerCrown", 1))
        self.assertEqual(default_durability("HelmetMidsummerCrown"), 100.0)

    def test_unknown_per_level_only_answers_quality_one(self):
        entry = {"base": 1000.0, "per_level": None}
        self.assertEqual(max_durability("x", 1, entry=entry), 1000.0)
        self.assertIsNone(max_durability("x", 2, entry=entry))

    def test_default_durability_is_the_quality_one_maximum(self):
        self.assertEqual(default_durability("SpearSplitner"), 300.0)
        self.assertEqual(default_durability("ArmorWolfChest"), 1000.0)
        self.assertEqual(default_durability("NotARealPrefab"), 100.0)


class DialogPercentTests(QtTestCase):
    def test_known_item_shows_percent_of_real_max(self):
        dialog = ItemEditDialog(item_data("SpearSplitner", durability=150.0))
        self.assertTrue(dialog.durability_percent.isVisibleTo(dialog))
        self.assertFalse(dialog.durability_input.isVisibleTo(dialog))
        self.assertAlmostEqual(dialog.durability_percent.value(), 50.0)
        self.assertIn("300", dialog.durability_label.text())

    def test_untouched_durability_is_preserved_exactly(self):
        original = 73.4567891
        dialog = ItemEditDialog(item_data("SpearSplitner", durability=original))
        self.assertIs(dialog.get_updated_data()["durability"], original)

    def test_percent_and_quality_changes_rewrite_the_absolute_value(self):
        dialog = ItemEditDialog(item_data("SpearSplitner", durability=150.0))
        dialog.durability_percent.setValue(100.0)
        self.assertEqual(dialog.get_updated_data()["durability"], 300.0)

        dialog = ItemEditDialog(item_data("SpearSplitner", durability=150.0))
        dialog.quality_input.setValue(3)
        self.assertIn("400", dialog.durability_label.text())
        self.assertEqual(dialog.get_updated_data()["durability"], 200.0)

    def test_unknown_item_falls_back_to_the_raw_field(self):
        dialog = ItemEditDialog(item_data("SomeModdedThing", durability=321.0))
        self.assertTrue(dialog.durability_input.isVisibleTo(dialog))
        self.assertFalse(dialog.durability_percent.isVisibleTo(dialog))
        self.assertEqual(dialog.get_updated_data()["durability"], 321.0)


if __name__ == "__main__":
    unittest.main()
