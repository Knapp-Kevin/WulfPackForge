import copy
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from subscripts.playerDataUtil import unpack_player_data_hex
from tests.fixture_saves import realistic_player_hex
from ui.appearancePreview import compose_preview
from ui.appearanceTab import AppearanceTab


APP = QApplication.instance() or QApplication([])

SKIN = [0.90, 0.60, 0.40]
HAIR = [0.10, 0.20, 0.90]  # unmistakably blue


def _distance(color: QColor, rgb) -> float:
    return abs(color.redF() - rgb[0]) + abs(color.greenF() - rgb[1]) + abs(color.blueF() - rgb[2])


def _first_pixel(image, predicate):
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            if c.alpha() > 200 and predicate(c):
                return x, y
    return None


class AppearancePreviewTests(unittest.TestCase):
    def test_colours_land_on_the_right_regions(self):
        pixmap = compose_preview("Hair7", "Beard3", SKIN, HAIR, 0, 256)
        self.assertFalse(pixmap.isNull())
        self.assertEqual((pixmap.width(), pixmap.height()), (256, 256))
        image = pixmap.toImage()
        blue = _first_pixel(image, lambda c: c.blueF() > 0.6 and c.redF() < 0.4)
        skin = _first_pixel(image, lambda c: c.redF() > 0.6 and c.blueF() < 0.45)
        self.assertIsNotNone(blue, "no hair-coloured pixel found")
        self.assertIsNotNone(skin, "no skin-coloured pixel found")
        self.assertLess(_distance(image.pixelColor(*blue), HAIR), _distance(image.pixelColor(*blue), SKIN))
        self.assertLess(_distance(image.pixelColor(*skin), SKIN), _distance(image.pixelColor(*skin), HAIR))

    def test_female_model_has_no_beard_and_matches_beardnone(self):
        bearded = compose_preview("Hair7", "Beard3", SKIN, HAIR, 0, 256).toImage()
        female = compose_preview("Hair7", "Beard3", SKIN, HAIR, 1, 256).toImage()
        no_beard = compose_preview("Hair7", "BeardNone", SKIN, HAIR, 0, 256).toImage()
        self.assertNotEqual(bearded, female)
        self.assertEqual(female, no_beard)

    def test_skin_change_leaves_hair_pixels_alone(self):
        a = compose_preview("Hair7", "BeardNone", SKIN, HAIR, 0, 256).toImage()
        b = compose_preview("Hair7", "BeardNone", [0.3, 0.2, 0.15], HAIR, 0, 256).toImage()
        self.assertNotEqual(a, b)
        blue = _first_pixel(a, lambda c: c.blueF() > 0.6 and c.redF() < 0.4)
        self.assertEqual(a.pixelColor(*blue).rgba(), b.pixelColor(*blue).rgba())

    def test_unknown_styles_fall_back_without_raising(self):
        pixmap = compose_preview("HairModded99", "BeardModded", SKIN, HAIR, 0, 128)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), 128)

    def test_hdr_spin_updates_the_preview(self):
        data = unpack_player_data_hex(realistic_player_hex())
        baseline = copy.deepcopy(data)
        tab = AppearanceTab()
        tab.load_data(data)
        before = tab.preview.pixmap().toImage()
        tab.overbright_checkbox.setChecked(True)
        tab.skin_hdr_spins[0].setValue(2.0)
        tab.skin_hdr_spins[1].setValue(0.1)
        tab.skin_hdr_spins[2].setValue(0.1)
        self.assertNotEqual(before, tab.preview.pixmap().toImage())
        self.assertEqual(data, baseline)

    def test_appearance_tab_preview_follows_selection(self):
        data = unpack_player_data_hex(realistic_player_hex())
        baseline = copy.deepcopy(data)
        tab = AppearanceTab()
        tab.load_data(data)
        before = tab.preview.pixmap().toImage()
        tab.hair_combo.setCurrentIndex(tab.hair_combo.findData("Hair13"))
        after = tab.preview.pixmap().toImage()
        self.assertNotEqual(before, after)
        self.assertEqual(tab.hair_combo.iconSize().width(), 72)
        self.assertEqual(data, baseline)  # preview never writes


if __name__ == "__main__":
    unittest.main()
