"""Every rewired signal still does its job; connections are bound methods, never self-capturing lambdas."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

import ui.inventoryTab as inv
import ui.newCharacterDialog as ncd
from subscripts.playerDataUtil import unpack_player_data_hex
from tests.fixture_saves import realistic_player_hex
from tests.test_razor import razor_violations
from ui.appearanceTab import AppearanceTab
from ui.characterPicker import CharacterPickerBar
from ui.itemEditDialog import ItemEditDialog
from ui.itemPickerDialog import ItemPickerDialog


APP = QApplication.instance() or QApplication([])


class SignalWiringTests(unittest.TestCase):
    def test_preset_button_click_scales_the_picked_colour(self):
        tab = AppearanceTab()
        data = unpack_player_data_hex(realistic_player_hex())
        data["skin_color"] = [0.5, 0.25, 0.125]
        tab.load_data(data)
        tab.overbright_checkbox.setChecked(True)
        tab.preset_target_combo.setCurrentIndex(tab.preset_target_combo.findData("skin"))
        QTest.mouseClick(tab.btn_preset_bright, Qt.LeftButton)
        self.assertEqual([round(v, 6) for v in tab.current_skin_rgb], [1.0, 0.5, 0.25])

    def test_slot_click_opens_picker_or_editor_for_that_slot(self):
        tab = inv.InventoryTab()
        tab.load_data(unpack_player_data_hex(realistic_player_hex()))
        filled = next(s for s in tab.slots.values() if s.item_data)
        empty = next(s for s in tab.slots.values() if s.item_data is None)
        with patch.object(inv, "ItemPickerDialog") as picker, patch.object(inv, "ItemEditDialog") as editor:
            picker.return_value.exec.return_value = QDialog.Rejected
            editor.return_value.exec.return_value = QDialog.Rejected
            QTest.mouseClick(empty, Qt.LeftButton)
            QTest.mouseClick(filled, Qt.LeftButton)
        picker.assert_called_once()
        editor.assert_called_once()
        self.assertIs(editor.call_args.args[0], filled.item_data)

    def test_refresh_button_runs_discovery_again(self):
        calls = []
        picker = CharacterPickerBar(discover=lambda: calls.append(1) or [])
        picker.refresh(None)
        picker.wait_for_scan()
        QTest.mouseClick(picker.btn_refresh_characters, Qt.LeftButton)
        picker.wait_for_scan()
        self.assertEqual(len(calls), 2)

    def test_new_character_colour_button_updates_the_colour(self):
        dialog = ncd.NewCharacterDialog()
        with patch.object(ncd.QColorDialog, "getColor", return_value=QColor(255, 0, 0)):
            QTest.mouseClick(dialog.btn_skin, Qt.LeftButton)
        self.assertEqual(dialog.skin_color, [1.0, 0.0, 0.0])

    def test_editing_finished_refreshes_the_catalog_status(self):
        dialog = ItemEditDialog({"prefab": "SwordBronze", "stack": 1, "durability": 100.0, "quality": 1, "variant": 0, "equipped": False})
        dialog.prefab_input.setText("SwordIron")
        dialog.prefab_input.editingFinished.emit()
        self.assertIn("Iron Sword", dialog.catalog_status.text())

    def test_double_click_accepts_the_picker(self):
        picker = ItemPickerDialog()
        picker.select_group("Helmets")
        picker.grid.setCurrentRow(0)
        picker.grid.itemDoubleClicked.emit(picker.grid.currentItem())
        self.assertEqual(picker.result(), QDialog.Accepted)
        self.assertTrue(picker.selected_prefab)

    def test_no_signal_is_connected_to_a_lambda_capturing_self(self):
        offenders = [v for v in razor_violations() if "lambda" in v]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
