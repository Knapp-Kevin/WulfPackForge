import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QComboBox

import subscripts.variantIcons as vi
import ui.glyphs as glyphs
import ui.variantPicker as vp
from subscripts.iconExtraction import INDEX_NAME
from tests.qt_support import QtTestCase
from ui.itemEditDialog import ItemEditDialog
from ui.inventorySlot import InventorySlot

APP = QApplication.instance() or QApplication([])


def _write_icon(path: Path, colour):
    image = QImage(8, 8, QImage.Format_ARGB32)
    image.fill(QColor(*colour))
    assert image.save(str(path))


def _cape_cache(temp: Path):
    cache = temp / "icons"
    cache.mkdir(parents=True)
    files = ["CapeLinen.png", "CapeLinen_1.png", "CapeLinen_2.png"]
    for name, colour in zip(files, ((200, 30, 30), (30, 60, 200), (240, 240, 240))):
        _write_icon(cache / name, colour)
    (cache / INDEX_NAME).write_text(json.dumps({"icons": {"CapeLinen": files}}), encoding="utf-8")
    return cache


class ColourNameTests(unittest.TestCase):
    def test_colour_words(self):
        self.assertEqual(vp.colour_name(QColor(200, 30, 30)), "red")
        self.assertEqual(vp.colour_name(QColor(30, 60, 200)), "blue")
        self.assertEqual(vp.colour_name(QColor(240, 240, 240)), "white")
        self.assertEqual(vp.colour_name(QColor(20, 20, 20)), "black")
        self.assertEqual(vp.colour_name(QColor(120, 80, 30)), "brown")
        self.assertEqual(vp.colour_name(QColor(60, 160, 60)), "green")
        self.assertEqual(vp.colour_name(QColor(0, 0, 0, 0)), "unknown")

    def test_average_ignores_transparent_pixels(self):
        image = QImage(2, 1, QImage.Format_ARGB32)
        image.setPixelColor(0, 0, QColor(0, 0, 255, 255))
        image.setPixelColor(1, 0, QColor(255, 0, 0, 0))
        self.assertEqual(vp.average_colour(image).name(), "#0000ff")


class VariantPickerTests(QtTestCase):
    def test_styles_come_from_the_extracted_icons_with_colour_words(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(vi, "default_workspace_root", return_value=Path(temp)):
            _cape_cache(Path(temp))
            self.assertEqual(vi.variant_count("CapeLinen"), 3)
            self.assertEqual(vi.variant_count("SwordBronze"), 0)
            combo = QComboBox()
            self.assertEqual(vp.populate_variant_combo(combo, "CapeLinen"), 3)
            self.assertEqual([combo.itemText(i) for i in range(3)], ["Style 0 · red", "Style 1 · blue", "Style 2 · white"])
            self.assertEqual(combo.itemData(2), 2)

    def test_editor_offers_styles_and_keeps_the_number_in_sync(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(vi, "default_workspace_root", return_value=Path(temp)), \
                patch.object(glyphs, "default_workspace_root", return_value=Path(temp)):
            _cape_cache(Path(temp))
            glyphs.clear_cache()
            dialog = ItemEditDialog({"prefab": "CapeLinen", "stack": 1, "quality": 1, "variant": 1, "durability": 100.0})
            self.assertEqual(dialog.variant_combo.count(), 3)
            self.assertEqual(dialog.variant_combo.currentIndex(), 1)
            dialog.variant_combo.setCurrentIndex(2)
            self.assertEqual(dialog.variant_input.value(), 2)
            dialog.variant_input.setValue(0)
            self.assertEqual(dialog.variant_combo.currentIndex(), 0)
            self.assertEqual(dialog.get_updated_data()["variant"], 0)
            preview = dialog.glyph_preview.pixmap().toImage().pixelColor(36, 36)
            self.assertEqual((preview.red(), preview.green(), preview.blue()), (200, 30, 30))
            dialog.prefab_input.setText("SwordBronze")
            dialog._reapply_constraints()
            self.assertFalse(dialog.variant_combo.isVisibleTo(dialog))

    def test_slot_shows_the_icon_of_its_variant(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(glyphs, "default_workspace_root", return_value=Path(temp)):
            _cape_cache(Path(temp))
            glyphs.clear_cache()
            slot = InventorySlot(0, 0)
            slot.set_item({"prefab": "CapeLinen", "stack": 1, "variant": 1})
            colour = slot.icon().pixmap(8, 8).toImage().pixelColor(4, 4)
            self.assertEqual((colour.red(), colour.green(), colour.blue()), (30, 60, 200))


if __name__ == "__main__":
    unittest.main()
