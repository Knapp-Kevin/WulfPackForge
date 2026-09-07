import copy
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from subscripts.playerDataUtil import unpack_player_data_hex
from tests.fixture_saves import realistic_player_hex
from ui.equipmentPanel import SLOT_ORDER, _display_name
from ui.inventoryTab import InventoryTab
from ui.itemEditDialog import ItemEditDialog


APP = QApplication.instance() or QApplication([])


def fixture():
    return unpack_player_data_hex(realistic_player_hex())


def loaded_tab():
    data = fixture()
    tab = InventoryTab()
    tab.load_data(data)
    return data, tab


class InventoryRemoveTests(unittest.TestCase):
    def test_delete_slot_item_removes_only_that_entry(self):
        data, tab = loaded_tab()
        before = copy.deepcopy(data["inventory"])
        target = data["inventory"][0]
        slot = tab.slots[(target["grid_x"], target["grid_y"])]

        tab.delete_slot_item(slot, confirm=False)

        self.assertNotIn(target, data["inventory"])
        self.assertIsNone(slot.item_data)
        self.assertEqual(data["inventory"], [entry for entry in before if entry != target])

    def test_editor_remove_button_finishes_with_remove_result(self):
        data, _tab = loaded_tab()
        dialog = ItemEditDialog(copy.deepcopy(data["inventory"][0]))
        dialog.remove()
        self.assertEqual(dialog.result(), ItemEditDialog.REMOVE)
        self.assertNotEqual(ItemEditDialog.REMOVE, ItemEditDialog.Accepted)

    def test_edit_flow_routes_remove_result_to_deletion(self):
        data, tab = loaded_tab()
        target = data["inventory"][0]
        slot = tab.slots[(target["grid_x"], target["grid_y"])]
        with mock.patch.object(ItemEditDialog, "exec", return_value=ItemEditDialog.REMOVE), \
                mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes) as question:
            tab.edit_slot_item(slot)
        self.assertNotIn(target, data["inventory"])
        self.assertIsNone(slot.item_data)
        self.assertIn(target["prefab"], question.call_args.args[2])

    def test_delete_key_removes_a_filled_slot_only(self):
        data, tab = loaded_tab()
        target = data["inventory"][0]
        count = len(data["inventory"])
        filled = tab.slots[(target["grid_x"], target["grid_y"])]
        empty = next(slot for slot in tab.slots.values() if slot.item_data is None)

        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            QTest.keyClick(empty, Qt.Key_Delete)
            self.assertEqual(len(data["inventory"]), count)
            QTest.keyClick(filled, Qt.Key_Delete)
        self.assertEqual(len(data["inventory"]), count - 1)
        self.assertNotIn(target, data["inventory"])

    def test_removing_an_equipped_item_updates_the_equipped_panel(self):
        data, tab = loaded_tab()
        equipped = next(entry for entry in data["inventory"] if entry.get("equipped"))
        slot = tab.slots[(equipped["grid_x"], equipped["grid_y"])]
        rows = lambda: " ".join(tab.equipment_panel.row_text(key) for key, _label in SLOT_ORDER)
        self.assertIn(_display_name(equipped), rows())
        tab.delete_slot_item(slot, confirm=False)
        self.assertNotIn(_display_name(equipped), rows())

    def test_usage_hint_names_every_gesture(self):
        _data, tab = loaded_tab()
        hint = tab.usage_hint.text().lower()
        for word in ("right-click", "drag", "delete", "remove"):
            self.assertIn(word, hint)


if __name__ == "__main__":
    unittest.main()
