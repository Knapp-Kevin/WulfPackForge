import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QComboBox

from data.appearance import BEARD_NONE, HAIR_NONE, VALHEIM_BEARDS, VALHEIM_HAIRS
from ui import glyphs as ui_glyphs


APP = QApplication.instance() or QApplication([])


class AppearanceTableTests(unittest.TestCase):
    def test_beard_table_from_catalog(self):
        self.assertEqual(VALHEIM_BEARDS["Beard20"], "Spiky")
        self.assertEqual(VALHEIM_BEARDS["Beard17"], "Neat")
        self.assertEqual(len(VALHEIM_BEARDS), 27)
        self.assertEqual(next(iter(VALHEIM_BEARDS)), BEARD_NONE)
        self.assertEqual(BEARD_NONE, "BeardNone")
        self.assertFalse(any("_" in key for key in VALHEIM_BEARDS))
        self.assertNotIn("nobeard", VALHEIM_BEARDS)

    def test_hair_table_from_catalog(self):
        self.assertEqual(VALHEIM_HAIRS["Hair7"], "Dragonslayer")
        self.assertEqual(len(VALHEIM_HAIRS), 38)
        self.assertEqual(next(iter(VALHEIM_HAIRS)), HAIR_NONE)
        self.assertEqual(HAIR_NONE, "HairNone")
        self.assertFalse(any("_" in key for key in VALHEIM_HAIRS))
        self.assertNotIn("nohair", VALHEIM_HAIRS)

    def test_legacy_modules_re_export_the_same_tables(self):
        self.assertTrue(VALHEIM_HAIRS and VALHEIM_BEARDS)  # the catalog tables are the only source now


class AppearanceThumbnailTests(unittest.TestCase):
    def setUp(self):
        ui_glyphs.clear_cache()

    def test_thumbnail_is_null_without_art_and_present_with_art(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.object(ui_glyphs, "glyph_root", return_value=root):
                self.assertTrue(ui_glyphs.appearance_pixmap("hair", "Hair7").isNull())
                (root / "hair").mkdir()
                image = QImage(64, 64, QImage.Format_ARGB32)
                image.fill(QColor(120, 120, 120, 255))
                image.save(str(root / "hair" / "Hair7.png"))
                ui_glyphs.clear_cache()
                pixmap = ui_glyphs.appearance_pixmap("hair", "Hair7")
                self.assertFalse(pixmap.isNull())
                self.assertEqual(pixmap.height(), 48)

                combo = QComboBox()
                ui_glyphs.populate_appearance_combo(combo, VALHEIM_HAIRS, "hair")
        self.assertEqual(combo.itemData(0, Qt.UserRole), HAIR_NONE)
        with_icon = [combo.itemData(i, Qt.UserRole) for i in range(combo.count()) if not combo.itemIcon(i).isNull()]
        self.assertEqual(with_icon, ["Hair7"])


if __name__ == "__main__":
    unittest.main()
