import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.itemEditDialog import ItemEditDialog


APP = QApplication.instance() or QApplication([])


def item_data(prefab, stack=1, quality=1, variant=0):
    return {
        "prefab": prefab,
        "stack": stack,
        "durability": 100.0,
        "quality": quality,
        "variant": variant,
        "equipped": False,
    }


class ItemEditDialogTests(unittest.TestCase):
    def test_known_item_uses_catalog_constraints(self):
        dialog = ItemEditDialog(item_data("ArrowWood", stack=20))
        self.assertIn("Valheim 0.221.12 catalog", dialog.catalog_status.text())
        self.assertEqual(dialog.stack_input.maximum(), 100)
        self.assertEqual(dialog.quality_input.maximum(), 1)
        self.assertEqual(dialog.variant_input.maximum(), 0)
        dialog.close()

    def test_existing_out_of_range_known_value_is_preserved(self):
        dialog = ItemEditDialog(item_data("ArrowWood", stack=250))
        self.assertEqual(dialog.stack_input.value(), 250)
        self.assertGreaterEqual(dialog.stack_input.maximum(), 250)
        self.assertIn("was preserved", dialog.catalog_status.text())
        dialog.close()

    def test_unknown_or_newer_item_keeps_raw_values(self):
        dialog = ItemEditDialog(
            item_data("MyModdedLegendaryHammer", stack=777, quality=42, variant=123)
        )
        updated = dialog.get_updated_data()
        self.assertEqual(updated["prefab"], "MyModdedLegendaryHammer")
        self.assertEqual(updated["stack"], 777)
        self.assertEqual(updated["quality"], 42)
        self.assertEqual(updated["variant"], 123)
        self.assertIn("Not found in the Valheim 0.221.12 catalog", dialog.catalog_status.text())
        self.assertIn("newer game version", dialog.catalog_status.text())
        dialog.close()

    def test_generated_catalog_item_is_human_readable(self):
        dialog = ItemEditDialog(item_data("ArmorAshlandsMediumChest"))
        self.assertIn("Breastplate of Ask", dialog.catalog_status.text())
        self.assertIn("Chest", dialog.catalog_status.text())
        dialog.close()

    def test_variant_row_only_for_items_with_styles_or_unknown(self):
        arrow = ItemEditDialog(item_data("ArrowWood", variant=0))
        self.assertTrue(arrow.variant_input.isHidden())
        self.assertEqual(arrow.get_updated_data()["variant"], 0)
        arrow.close()
        shield = ItemEditDialog(item_data("ShieldWood", variant=3))
        self.assertFalse(shield.variant_input.isHidden())
        self.assertEqual(shield.variant_input.maximum(), 7)
        self.assertEqual(shield.get_updated_data()["variant"], 3)
        shield.close()
        modded = ItemEditDialog(item_data("MyModdedLegendaryHammer", variant=5))
        self.assertFalse(modded.variant_input.isHidden())
        self.assertEqual(modded.get_updated_data()["variant"], 5)
        modded.close()

    def test_catalog_completion_normalizes_to_prefab(self):
        dialog = ItemEditDialog(item_data("ArrowWood"))
        dialog._completion_selected("Bronze Sword — SwordBronze")
        self.assertEqual(dialog.prefab_input.text(), "SwordBronze")
        self.assertEqual(dialog.stack_input.maximum(), 1)
        self.assertEqual(dialog.quality_input.maximum(), 4)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
