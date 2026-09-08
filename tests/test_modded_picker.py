import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from data.item_groups import GROUPS, MODDED, items_under, navigation_tree, pickable_items
from data.items import EXTRA_ITEMS, ItemDefinition, clear_registered_items, register_items, resolve_item
from tests.qt_support import QtTestCase
from ui.itemPickerDialog import ItemPickerDialog

APP = QApplication.instance() or QApplication([])

MODDED_ITEMS = [
    ItemDefinition(prefab="VACrossbowModer", display_name="Dragonfrost Crossbow", max_stack=1, max_quality=4, item_type="Bow"),
    ItemDefinition(prefab="BackpackBlackForest", display_name="Rugged Backpack", max_stack=1, max_quality=1, item_type="Shoulder"),
    ItemDefinition(prefab="Beard99", display_name="Mod Beard", item_type="Customization"),
]


class ModdedGroupTests(unittest.TestCase):
    def setUp(self):
        clear_registered_items()  # an earlier module may have left registrations behind

    def tearDown(self):
        clear_registered_items()

    def test_no_modded_node_without_registered_items(self):
        self.assertEqual([group for group, _ in navigation_tree()], list(GROUPS))
        self.assertEqual(items_under(MODDED), [])

    def test_registered_items_form_a_modded_group_branched_by_vanilla_group(self):
        self.assertEqual(register_items(MODDED_ITEMS), 3)
        tree = dict(navigation_tree())
        self.assertEqual([subgroup for subgroup, _ in tree[MODDED]], ["Bows and Ammo", "Capes"])
        self.assertEqual([item.prefab for item in items_under(MODDED)], ["VACrossbowModer", "BackpackBlackForest"])
        self.assertEqual([item.prefab for item in items_under(MODDED, "Bows and Ammo")], ["VACrossbowModer"])
        self.assertIn("VACrossbowModer", [item.prefab for item in pickable_items()])
        self.assertNotIn("Beard99", [item.prefab for item in pickable_items()])  # customisation is never pickable
        clear_registered_items()
        self.assertEqual(EXTRA_ITEMS, [])
        self.assertIsNone(resolve_item("VACrossbowModer"))


class ModdedPickerTests(QtTestCase):
    def tearDown(self):
        clear_registered_items()
        super().tearDown()

    def test_picker_lists_modded_items_and_finds_them_by_search(self):
        register_items(MODDED_ITEMS)
        dialog = ItemPickerDialog()
        labels = [dialog.categories.topLevelItem(i).data(0, Qt.UserRole)[0] for i in range(dialog.categories.topLevelItemCount())]
        self.assertEqual(labels[-2:], [MODDED, "Advanced"])
        dialog.select_group(MODDED)
        prefabs = [dialog.grid.item(i).data(Qt.UserRole) for i in range(dialog.grid.count())]
        self.assertEqual(prefabs, ["VACrossbowModer", "BackpackBlackForest"])
        dialog.search.setText("dragonfrost")
        self.assertEqual([dialog.grid.item(i).data(Qt.UserRole) for i in range(dialog.grid.count())], ["VACrossbowModer"])
        dialog.grid.setCurrentRow(0)
        dialog.accept()
        self.assertEqual(dialog.selected_prefab, "VACrossbowModer")


if __name__ == "__main__":
    unittest.main()
