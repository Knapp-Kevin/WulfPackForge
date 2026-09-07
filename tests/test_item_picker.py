import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from data.item_groups import GROUPS
from ui.inventorySlot import InventorySlot
from ui.itemPickerDialog import ItemPickerDialog


APP = QApplication.instance() or QApplication([])


def _grid_prefabs(dialog):
    return [dialog.grid.item(i).data(Qt.UserRole) for i in range(dialog.grid.count())]


class ItemPickerDialogTests(unittest.TestCase):
    def test_categories_are_listed_in_order_with_advanced_last(self):
        dialog = ItemPickerDialog()
        labels = [dialog.categories.topLevelItem(i).data(0, Qt.UserRole)[0] for i in range(dialog.categories.topLevelItemCount())]
        self.assertEqual(labels, list(GROUPS) + ["Advanced"])
        dialog.close()

    def test_tree_labels_carry_counts_and_breadcrumb(self):
        from data.item_groups import items_in_group
        from ui.itemPickerDialog import ICON_SIZE
        dialog = ItemPickerDialog()
        weapons = dialog.categories.topLevelItem(0)
        self.assertEqual(weapons.text(0), f"Weapons ({len(items_in_group('Weapons'))})")
        swords = next(weapons.child(i) for i in range(weapons.childCount()) if weapons.child(i).text(0).startswith("Swords"))
        bronze = next(swords.child(i) for i in range(swords.childCount()) if swords.child(i).text(0).startswith("Bronze"))
        dialog.categories.setCurrentItem(bronze)
        self.assertEqual(dialog.breadcrumb.text(), "Weapons › Swords › Bronze")
        row = dialog.grid.item(0)
        self.assertEqual(row.text(), "Bronze Sword\nBronze")
        self.assertEqual(ICON_SIZE, 96)
        dialog.close()

    def test_tree_branches_weapons_into_type_and_material(self):
        dialog = ItemPickerDialog()
        weapons = dialog.categories.topLevelItem(0)
        swords = next(weapons.child(i) for i in range(weapons.childCount()) if weapons.child(i).data(0, Qt.UserRole)[1] == "Swords")
        bronze = next(swords.child(i) for i in range(swords.childCount()) if swords.child(i).data(0, Qt.UserRole)[2] == "Bronze")
        dialog.categories.setCurrentItem(bronze)
        self.assertEqual(_grid_prefabs(dialog), ["SwordBronze"])
        dialog.categories.setCurrentItem(weapons)
        self.assertIn("SwordIron", _grid_prefabs(dialog))
        dialog.close()

    def test_clothing_separate_and_creature_gear_absent(self):
        dialog = ItemPickerDialog()
        dialog.select_group("Clothing and Hats")
        prefabs = _grid_prefabs(dialog)
        self.assertIn("ArmorDress4", prefabs)
        self.assertNotIn("ArmorFenringChest", prefabs)
        row = dialog.grid.item(prefabs.index("ArmorDress4"))
        self.assertIn("clothing", row.toolTip().lower())
        dialog.search.setText("goblin")
        self.assertNotIn("GoblinArmband", _grid_prefabs(dialog))
        dialog.search.setText("log")
        self.assertNotIn("troll_log_swing_h", _grid_prefabs(dialog))
        last = dialog.categories.topLevelItem(dialog.categories.topLevelItemCount() - 2).data(0, Qt.UserRole)[0]
        self.assertEqual(last, "Misc")
        dialog.close()

    def test_selecting_weapons_shows_sword_with_icon(self):
        dialog = ItemPickerDialog()
        dialog.select_group("Weapons")
        prefabs = _grid_prefabs(dialog)
        self.assertIn("SwordBronze", prefabs)
        row = dialog.grid.item(prefabs.index("SwordBronze"))
        self.assertEqual(row.text().splitlines()[0], "Bronze Sword")
        self.assertFalse(row.icon().isNull())
        dialog.close()

    def test_search_spans_all_groups(self):
        dialog = ItemPickerDialog()
        dialog.select_group("Weapons")
        dialog.search.setText("acorn")
        self.assertEqual(_grid_prefabs(dialog), ["Acorn"])
        dialog.search.setText("")
        self.assertIn("SwordBronze", _grid_prefabs(dialog))
        dialog.close()

    def test_selecting_grid_item_sets_prefab(self):
        dialog = ItemPickerDialog()
        dialog.select_group("Weapons")
        prefabs = _grid_prefabs(dialog)
        dialog.grid.setCurrentRow(prefabs.index("SwordBronze"))
        dialog.accept()
        self.assertEqual(dialog.selected_prefab, "SwordBronze")
        self.assertEqual(dialog.result(), QDialog.Accepted)

    def test_advanced_accepts_raw_prefab(self):
        dialog = ItemPickerDialog()
        dialog.select_group("Advanced")
        dialog.raw_input.setText("  MyModdedHammer ")
        dialog.accept()
        self.assertEqual(dialog.selected_prefab, "MyModdedHammer")
        self.assertEqual(dialog.result(), QDialog.Accepted)

    def test_ok_with_nothing_selected_keeps_dialog_open(self):
        dialog = ItemPickerDialog()
        dialog.select_group("Weapons")
        dialog.grid.setCurrentRow(-1)
        dialog.accept()
        self.assertIsNone(dialog.selected_prefab)
        self.assertNotEqual(dialog.result(), QDialog.Accepted)
        dialog.close()


class InventorySlotIconTests(unittest.TestCase):
    def test_slot_shows_icon_for_item_and_none_when_empty(self):
        slot = InventorySlot(0, 0)
        self.assertTrue(slot.icon().isNull())
        slot.set_item({"prefab": "SwordBronze", "stack": 1, "equipped": False, "quality": 1, "variant": 0})
        self.assertFalse(slot.icon().isNull())
        slot.clear_item()
        self.assertTrue(slot.icon().isNull())


if __name__ == "__main__":
    unittest.main()
