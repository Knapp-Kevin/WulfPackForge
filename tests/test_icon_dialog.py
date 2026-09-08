import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

import ui.glyphs as glyphs
import ui.iconExtractionDialog as dlg
import ui.inventoryTab as inv
from subscripts.iconExtraction import BUNDLES_RELATIVE, ExtractionReport
from tests.qt_support import QtTestCase

APP = QApplication.instance() or QApplication([])


def _fake_extract(game_dir, prefabs, cache_dir, progress=None):
    if progress:
        progress("Saving icons", 1, 1)
    image = QImage(8, 8, QImage.Format_ARGB32)
    image.fill(QColor(0, 200, 0))
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    image.save(str(Path(cache_dir) / "SwordBronze.png"))
    return ExtractionReport(str(game_dir), str(cache_dir), requested=len(list(prefabs)), extracted=1, seconds=0.1)


class IconExtractionDialogTests(QtTestCase):
    def test_dialog_refuses_without_the_optional_package(self):
        with patch.object(dlg, "extraction_available", return_value=False):
            dialog = dlg.IconExtractionDialog(game_dir=None, cache_dir="unused")
        self.assertFalse(dialog.btn_extract.isEnabled())
        self.assertIn("UnityPy", dialog.status.text())

    def test_dialog_rejects_a_folder_without_bundles(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(dlg, "extraction_available", return_value=True):
            dialog = dlg.IconExtractionDialog(game_dir=Path(temp), cache_dir=Path(temp) / "icons")
            dialog.start()
            self.assertIn("does not contain", dialog.status.text())
            self.assertIsNone(dialog._future)

    def test_dialog_runs_the_extraction_and_the_tiles_pick_up_the_icon(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(dlg, "extraction_available", return_value=True), \
                patch.object(dlg, "extract_icons", _fake_extract), \
                patch.object(glyphs, "default_workspace_root", return_value=Path(temp)):
            game = Path(temp) / "game"
            (game / BUNDLES_RELATIVE).mkdir(parents=True)
            cache = Path(temp) / "icons"
            glyphs.clear_cache()
            before = glyphs.item_pixmap("SwordBronze", 8).toImage().pixelColor(4, 4)
            dialog = dlg.IconExtractionDialog(game_dir=game, cache_dir=cache)
            reports = []
            dialog.extracted.connect(reports.append)
            dialog.start()
            for _ in range(200):
                APP.processEvents()
                if reports:
                    break
                dialog._check()
            self.assertEqual(len(reports), 1)
            self.assertIn("Extracted 1 of", dialog.status.text())
            self.assertTrue(dialog.btn_extract.isEnabled())
            glyphs.clear_cache()
            after = glyphs.item_pixmap("SwordBronze", 8).toImage().pixelColor(4, 4)
            self.assertNotEqual(before, after)
            self.assertEqual((after.red(), after.green(), after.blue()), (0, 200, 0))
            dialog.shutdown()

    def test_inventory_tab_refreshes_tiles_after_extraction(self):
        tab = inv.InventoryTab()
        tab.load_data({"inventory": [{"name": "SwordBronze", "grid_x": 0, "grid_y": 0, "stack": 1, "quality": 1, "variant": 0}]})
        with patch.object(glyphs, "clear_cache") as cleared, patch.object(inv, "clear_cache", cleared):
            tab._icons_extracted(ExtractionReport("g", "c"))
        cleared.assert_called_once()
        self.assertTrue(tab.btn_game_icons.isEnabled())


if __name__ == "__main__":
    unittest.main()
