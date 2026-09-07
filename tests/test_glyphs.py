import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QGuiApplication, QImage, QPixmap

from data.glyphs import TINTS, glyph_for
from data.items import resolve_item
from ui import glyphs as ui_glyphs


APP = QGuiApplication.instance() or QGuiApplication([])


class GlyphResolutionTests(unittest.TestCase):
    def test_known_items_resolve_to_glyph_and_tint(self):
        self.assertEqual(glyph_for(resolve_item("SwordBronze")), ("G01_sword", "bronze"))
        self.assertEqual(glyph_for(resolve_item("ArrowIron")), ("G13_arrow", "iron"))
        self.assertEqual(glyph_for(resolve_item("HelmetBronze")), ("G15_helmet", "bronze"))
        self.assertEqual(glyph_for(resolve_item("Wood")), ("G20_ingot", "wood"))

    def test_refined_glyph_ids(self):
        from data.glyphs import GLYPH_IDS, PENDING_GLYPH_IDS
        expected = {
            "BombOoze": "G24_bomb", "BombBlob_Frost": "G24_bomb", "PickaxeIron": "G25_pickaxe",
            "Hammer": "G26_hammer", "Hoe": "G27_hoe", "Cultivator": "G27_hoe", "CryptKey": "G28_key",
            "HildirKey_forestcrypt": "G28_key", "DragonEgg": "G29_egg", "SaddleLox": "G30_misc",
            "Feaster": "G30_misc", "Tankard": "G31_tankard", "FishingRod": "G32_fishing",
            "FishingBait": "G32_fishing", "FistBjornClaw": "G33_fist", "Scythe": "G34_scythe",
            "THSwordKrom": "G06_greatsword", "Torch": "G23_torch",
        }
        for prefab, glyph in expected.items():
            self.assertEqual(glyph_for(resolve_item(prefab))[0], glyph, prefab)
        # Ids migrate from PENDING_GLYPH_IDS to GLYPH_IDS as their masters are committed.
        self.assertFalse(set(PENDING_GLYPH_IDS) & set(GLYPH_IDS))
        self.assertEqual(len(set(PENDING_GLYPH_IDS) | set(GLYPH_IDS)), 34)
        for glyph in set(expected.values()):
            self.assertIn(glyph, set(PENDING_GLYPH_IDS) | set(GLYPH_IDS), glyph)

    def test_pending_glyph_renders_placeholder(self):
        ui_glyphs.clear_cache()
        pixmap = ui_glyphs.item_pixmap("BombOoze", 64)
        self.assertFalse(pixmap.isNull())
        self.assertGreater(pixmap.toImage().pixelColor(32, 32).alpha(), 0)

    def test_unknown_prefab_falls_back_to_slate_ingot(self):
        self.assertEqual(glyph_for(None), ("G20_ingot", "slate"))
        self.assertEqual(glyph_for(resolve_item("MyModdedLegendaryHammer")), ("G20_ingot", "slate"))
        self.assertIn("slate", TINTS)


class GlyphRenderTests(unittest.TestCase):
    def setUp(self):
        ui_glyphs.clear_cache()

    def test_item_pixmap_renders_placeholder_without_master(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(ui_glyphs, "master_dir", return_value=Path(temp_dir)):
                pixmap = ui_glyphs.item_pixmap("SwordBronze", 64)
        self.assertFalse(pixmap.isNull())
        self.assertEqual((pixmap.width(), pixmap.height()), (64, 64))
        centre = pixmap.toImage().pixelColor(32, 32)
        self.assertGreater(centre.alpha(), 0)

    def test_tint_pixmap_keeps_alpha_and_applies_colour(self):
        image = QImage(4, 4, QImage.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        image.setPixelColor(1, 1, QColor(200, 200, 200, 255))
        tinted = ui_glyphs.tint_pixmap(QPixmap.fromImage(image), QColor("#b07a2a")).toImage()
        self.assertEqual(tinted.pixelColor(0, 0).alpha(), 0)
        centre = tinted.pixelColor(1, 1)
        self.assertEqual(centre.alpha(), 255)
        self.assertGreater(centre.red(), centre.blue())

    def test_master_png_is_used_and_tinted_when_present(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            master = QImage(64, 64, QImage.Format_ARGB32)
            master.fill(QColor(180, 180, 180, 255))
            master.save(os.path.join(temp_dir, "G01_sword.png"))
            with patch.object(ui_glyphs, "master_dir", return_value=Path(temp_dir)):
                pixmap = ui_glyphs.item_pixmap("SwordBronze", 64)
        colour = pixmap.toImage().pixelColor(32, 32)
        self.assertEqual(colour.alpha(), 255)
        self.assertGreater(colour.red(), colour.blue())  # bronze tint applied to the grey master

    def test_item_icon_is_not_null(self):
        self.assertFalse(ui_glyphs.item_icon("Wood").isNull())

    def test_all_item_masters_are_decodable_transparent_runtime_assets(self):
        self.assertTrue(ui_glyphs.glyph_bundle_is_usable())

    def test_all_appearance_thumbnails_are_decodable_runtime_assets(self):
        self.assertTrue(ui_glyphs.appearance_bundle_is_usable())


if __name__ == "__main__":
    unittest.main()
