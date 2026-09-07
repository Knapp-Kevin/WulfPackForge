import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import ui.inventoryTab as inv
import ui.mainWindow as mw
from subscripts.logSetup import install_excepthook
from tests.fixture_saves import realistic_root_save, write_fch


APP = QApplication.instance() or QApplication([])


class NoCharacterStateTests(unittest.TestCase):
    def test_tabs_are_disabled_until_a_character_loads(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(mw, "discover_character_records", return_value=[]), \
                patch("subscripts.workspace.default_workspace_root", return_value=Path(temp) / "workspace"):
            window = mw.MainWindow(startup_warning=False)
            self.assertFalse(window.tabs.isEnabled())
            self.assertIn("Open Character", window.file_label.text())
            source = write_fch(Path(temp) / "hero.fch", realistic_root_save())
            window.load_save_file(str(source))
            self.assertTrue(window.tabs.isEnabled())
            self.assertTrue(window.file_label.text().startswith("Editing"))
            window.close()

    def test_inventory_actions_refuse_without_a_character(self):
        tab = inv.InventoryTab()
        slot = next(iter(tab.slots.values()))
        with patch.object(inv, "ItemPickerDialog") as picker, patch.object(inv, "ItemEditDialog") as editor:
            tab.on_slot_clicked(slot)
            tab.add_item_to_slot(slot)
            tab.edit_slot_item(slot)
            tab.delete_slot_item(slot, confirm=False)
        picker.assert_not_called()
        editor.assert_not_called()

    def test_unhandled_exceptions_are_logged(self):
        previous = sys.excepthook
        try:
            install_excepthook()
            with self.assertLogs("wulfpack-forge", level="ERROR") as logs:
                try:
                    raise RuntimeError("boom in a slot")
                except RuntimeError:
                    sys.excepthook(*sys.exc_info())
            self.assertTrue(any("boom in a slot" in line for line in logs.output), logs.output)
        finally:
            sys.excepthook = previous


if __name__ == "__main__":
    unittest.main()
