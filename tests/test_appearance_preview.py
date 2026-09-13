import copy
import os
import unittest
from tests.qt_support import QtTestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from subscripts.playerDataUtil import unpack_player_data_hex
from tests.fixture_saves import realistic_player_hex
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from ui.appearancePreview import _ANCHORS, ColorSwatch, beard_transform, compose_preview, display_color, split_layers
from ui.previewLayers import _anchor, _light_runs, _without_crown
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


class AppearancePreviewTests(QtTestCase):
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

    def test_real_thumbnails_anchor_on_the_shoulder_line(self):
        for kind, key in (("hair", "Hair7"), ("hair", "Hair29"), ("beard", "Beard3"), ("beard", "Beard20")):
            split_layers(kind, key, 256)
        # (kind, key, shoulder line, lowest dark row) measured in the phase 47 research
        for kind, key, top, bottom in (("hair", "Hair7", 201, 226), ("hair", "Hair29", 208, 233),
                                       ("beard", "Beard3", 193, 222), ("beard", "Beard20", 188, 236)):
            left, right, line, low = _ANCHORS[(kind, key, 256)]
            self.assertEqual((line, low), (top, bottom), (kind, key))
            self.assertGreaterEqual(low - line, 20, (kind, key))
            self.assertTrue(175 <= right - left <= 215, (kind, key, right - left))
        scale, dx, dy = beard_transform("Hair7", "Beard3", 256)
        self.assertTrue(0.85 < scale < 1.0, scale)
        self.assertAlmostEqual(dy, 201 - 193 * scale, delta=0.5)
        pixmap = compose_preview("Hair7", "Beard3", SKIN, HAIR, 0, 256)
        self.assertEqual((pixmap.width(), pixmap.height()), (256, 256))
        self.assertEqual(beard_transform("Hair7", "BeardNone", 256)[0], 1.0)

    def test_a_hair_whose_outline_hides_the_shoulders_is_clamped(self):
        split_layers("hair", "Hair6", 256)
        split_layers("beard", "Beard3", 256)
        self.assertEqual(_ANCHORS[("hair", "Hair6", 256)][2:], (175, 237))
        scale, dx, dy = beard_transform("Hair6", "Beard3", 256)
        self.assertAlmostEqual(dy, 198.6 - 193 * scale, delta=0.01)  # 237 - 0.15 * 256, unrounded
        bust = {y: (78, 178) for y in range(200)}
        bust.update({y: (28, 228) for y in range(200, 256)})
        self.assertEqual(_anchor(bust, 256), (28, 228, 200, 255))
        growing = {y: (20 - y // 32, 220 + y // 32) for y in range(256)}  # 92 percent wide at the top
        self.assertEqual(_anchor(growing, 256)[2], 0)
        self.assertEqual(_anchor({}, 256), (0, 0, 0, 0))

    def test_the_crown_highlight_is_masked_out_of_the_beard_layer(self):
        layer = split_layers("beard", "Beard3", 256)[1].toImage()
        crown = [y for y in range(45, 109) for x in range(256) if layer.pixelColor(x, y).alpha() > 0]
        self.assertEqual(crown, [])
        body = any(layer.pixelColor(x, y).alpha() > 0 for y in range(114, 181) for x in range(256))
        self.assertTrue(body)
        synthetic = QImage(64, 256, QImage.Format_ARGB32)
        synthetic.fill(Qt.transparent)
        for y in list(range(40, 61)) + list(range(120, 151)):
            synthetic.setPixelColor(10, y, QColor(200, 200, 200))
        synthetic.setPixelColor(10, 90, QColor(200, 200, 200, 100))  # below the alpha threshold: not a light row
        self.assertEqual(_light_runs(synthetic), [(40, 60), (120, 150)])
        masked = _without_crown(synthetic, 256)
        self.assertEqual(_light_runs(masked), [(120, 150)])
        whole = split_layers("beard", "Beard11", 256)[1].toImage()
        self.assertTrue(any(whole.pixelColor(x, 44).alpha() > 0 for x in range(256)))

    def test_overbright_skin_keeps_its_hue(self):
        color, peak = display_color([2.0, 1.0, 0.5])
        self.assertEqual(peak, 2.0)
        self.assertEqual((color.red(), color.green(), color.blue()), (255, 127, 63))
        image = compose_preview("Hair7", "BeardNone", [2.0, 1.0, 0.5], [0.2, 0.1, 0.05], 0, 256).toImage()
        face = _first_pixel(image, lambda c: c.redF() > 0.8 and c.alpha() == 255)
        self.assertIsNotNone(face)
        pixel = image.pixelColor(*face)
        self.assertGreater(pixel.redF() - pixel.blueF(), 0.3, "overbright skin washed to white")

    def test_overbright_hair_blooms_outside_the_silhouette(self):
        plain = compose_preview("Hair7", "BeardNone", SKIN, [0.1, 0.2, 0.8], 0, 256).toImage()
        bright = compose_preview("Hair7", "BeardNone", SKIN, [0.4, 0.8, 3.2], 0, 256).toImage()
        lit_outside = [
            (x, y) for y in range(plain.height()) for x in range(plain.width())
            if plain.pixelColor(x, y).alpha() == 0 and bright.pixelColor(x, y).alpha() > 0
        ]
        self.assertGreater(len(lit_outside), 100, "no bloom beyond the silhouette")

    def test_swatch_shows_hue_and_rim(self):
        swatch = ColorSwatch()
        swatch.resize(100, 30)
        swatch.set_color([2.0, 1.0, 0.5])
        hot = swatch.grab().toImage()
        centre = hot.pixelColor(50, 15)
        self.assertGreater(centre.redF(), 0.9)
        self.assertLess(centre.blueF(), 0.4)
        swatch.set_color([1.0, 0.5, 0.25])
        cool = swatch.grab().toImage()
        hot_rim, cool_rim = hot.pixelColor(2, 2), cool.pixelColor(2, 2)
        self.assertLess(abs(cool_rim.redF() - cool_rim.blueF()), 0.05, "1x rim should be the plain background")
        self.assertGreater(hot_rim.redF() - hot_rim.blueF(), 0.15, "overbright rim should carry the colour")

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
