import os
import unittest
from tests.qt_support import QtTestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from data.durability import default_durability, durability_entry, max_durability
from tools.update_item_durability import parse_page
from ui.itemEditDialog import ItemEditDialog


APP = QApplication.instance() or QApplication([])

SPLITNIR_PAGE = """{{infobox weapon
| title          = Splitnir
| id             = SpearSplitner
| type           = Spear
|stamina=16}}
The '''Splitnir''' is the sixth spear.

==Upgrade information==
{| class="article-table"
!Quality
!1
!2
!3
!4
|-
!Pierce
|135
|141
|147
|153
|-
!Durability
|100
|150
|200
|250
|-
!Crafting
|10 Ashwood
|5 Ashwood
|10 Ashwood
|15 Ashwood
{{Upgrade station row|Black forge|4|start=3}}
"""

LEATHER_PAGE = """{{Infobox armor
| title = Leather Helmet
| id = HelmetLeather
| durability     = 400
| durability per level = 100
}}
{{Infobox armor
| title = Leather Tunic
| id = ArmorLeatherChest
| durability     = 400
| durability per level = 100
}}
{{Infobox armor
| title = Leather Pants
| id = ArmorLeatherLegs
| durability     = 400
| durability per level = 100
}}
Some prose about the set.
"""

CROWN_PAGE = """{{Infobox armor
| title = Midsummer Crown
| id = HelmetMidsummerCrown
| durability = 0
}}
"""


SET_PAGE = """{{Infobox armor
| title = Bronze Helmet
| id = HelmetBronze
| durability     = 1000
}}
{{Infobox armor
| title = Bronze Plate Cuirass
| id = ArmorBronzeChest
| durability     = 1000
}}
<tabber>
1=
=== Quality 1 ===
Forge level: 1<br>
Durability per piece: 1000
|-|
2=
=== Quality 2 ===
Forge level: 2<br>
Durability per piece: 1200
|-|
3=
=== Quality 3 ===
Durability per piece: 1400
|-|
4=
=== Quality 4 ===
Durability per piece: 1600
</tabber>
"""


def item_data(prefab, durability=100.0, quality=1):
    return {"prefab": prefab, "stack": 1, "durability": durability, "quality": quality, "variant": 0, "equipped": False}


class ParserTests(QtTestCase):
    def test_upgrade_table_gives_levels_base_and_per_level(self):
        table = parse_page(SPLITNIR_PAGE)
        entry = table["SpearSplitner"]
        self.assertEqual(entry["levels"], [100.0, 150.0, 200.0, 250.0])
        self.assertEqual((entry["base"], entry["per_level"]), (100.0, 50.0))

    def test_set_page_yields_one_entry_per_infobox(self):
        table = parse_page(LEATHER_PAGE)
        self.assertEqual(set(table), {"HelmetLeather", "ArmorLeatherChest", "ArmorLeatherLegs"})
        for entry in table.values():
            self.assertEqual((entry["base"], entry["per_level"]), (400.0, 100.0))

    def test_set_page_quality_tabs_supply_the_per_level_figure(self):
        table = parse_page(SET_PAGE)
        self.assertEqual(table["HelmetBronze"]["levels"], [1000.0, 1200.0, 1400.0, 1600.0])
        self.assertEqual((table["ArmorBronzeChest"]["base"], table["ArmorBronzeChest"]["per_level"]), (1000.0, 200.0))

    def test_zero_durability_is_kept_as_indestructible(self):
        self.assertEqual(parse_page(CROWN_PAGE)["HelmetMidsummerCrown"]["base"], 0.0)


class MaxDurabilityTests(QtTestCase):
    def test_shipped_table_arithmetic(self):
        self.assertEqual(max_durability("SpearSplitner", 1), 100.0)
        self.assertEqual(max_durability("SpearSplitner", 3), 200.0)
        self.assertIsNone(max_durability("Tankard", 1))
        self.assertIsNone(max_durability("NotARealPrefab", 1))
        self.assertIsNotNone(durability_entry("ArmorWolfChest"))

    def test_unknown_per_level_only_answers_quality_one(self):
        entry = {"base": 1000.0, "per_level": None}
        self.assertEqual(max_durability("x", 1, entry=entry), 1000.0)
        self.assertIsNone(max_durability("x", 2, entry=entry))

    def test_default_durability_is_the_quality_one_maximum(self):
        self.assertEqual(default_durability("SpearSplitner"), 100.0)
        self.assertEqual(default_durability("ArmorWolfChest"), 1000.0)
        self.assertEqual(default_durability("NotARealPrefab"), 100.0)


class DialogPercentTests(QtTestCase):
    def test_known_item_shows_percent_of_real_max(self):
        dialog = ItemEditDialog(item_data("SpearSplitner", durability=50.0))
        self.assertTrue(dialog.durability_percent.isVisibleTo(dialog))
        self.assertFalse(dialog.durability_input.isVisibleTo(dialog))
        self.assertAlmostEqual(dialog.durability_percent.value(), 50.0)
        self.assertIn("100", dialog.durability_label.text())

    def test_untouched_durability_is_preserved_exactly(self):
        original = 73.4567891
        dialog = ItemEditDialog(item_data("SpearSplitner", durability=original))
        self.assertIs(dialog.get_updated_data()["durability"], original)

    def test_percent_and_quality_changes_rewrite_the_absolute_value(self):
        dialog = ItemEditDialog(item_data("SpearSplitner", durability=50.0))
        dialog.durability_percent.setValue(100.0)
        self.assertEqual(dialog.get_updated_data()["durability"], 100.0)

        dialog = ItemEditDialog(item_data("SpearSplitner", durability=50.0))
        dialog.quality_input.setValue(3)
        self.assertIn("200", dialog.durability_label.text())
        self.assertEqual(dialog.get_updated_data()["durability"], 100.0)

    def test_unknown_item_falls_back_to_the_raw_field(self):
        dialog = ItemEditDialog(item_data("SomeModdedThing", durability=321.0))
        self.assertTrue(dialog.durability_input.isVisibleTo(dialog))
        self.assertFalse(dialog.durability_percent.isVisibleTo(dialog))
        self.assertEqual(dialog.get_updated_data()["durability"], 321.0)


if __name__ == "__main__":
    unittest.main()
