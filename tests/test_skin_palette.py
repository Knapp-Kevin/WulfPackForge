import unittest

from data.skinPalette import (
    LIGHTNESS_NUDGE, PALETTE_ATTRIBUTION, SKIN_CEIL, SKIN_FLOOR, is_palette_tint, nearest_tone, nudged, palette_tints,
)

FORM_B = [(1.0, 0.963, 0.927), (0.922, 0.877, 0.831), (0.844, 0.8, 0.711), (0.767, 0.714, 0.609), (0.689, 0.606, 0.481),
          (0.611, 0.481, 0.328), (0.533, 0.377, 0.275), (0.456, 0.308, 0.247), (0.378, 0.319, 0.274), (0.3, 0.263, 0.234)]


def _r3(tint):
    return tuple(round(c, 3) for c in tint)


class SkinPaletteTests(unittest.TestCase):
    def test_form_b_tints_match_the_measured_table(self):
        self.assertEqual([_r3(t) for t in palette_tints()], FORM_B)
        self.assertIn("Monk Skin Tone", PALETTE_ATTRIBUTION)
        self.assertIn("CC BY 4.0", PALETTE_ATTRIBUTION)

    def test_nudge_moves_lightness_and_clamps(self):
        tones = palette_tints()
        self.assertAlmostEqual(max(nudged(tones[9], -0.1)), SKIN_FLOOR)
        self.assertAlmostEqual(max(nudged(tones[0], +0.1)), SKIN_CEIL)
        moved = nudged(tones[4], +0.05)
        self.assertAlmostEqual(max(moved), max(tones[4]) + 0.05)
        for a, b in zip(moved, tones[4]):
            self.assertAlmostEqual(a / max(moved), b / max(tones[4]))

    def test_is_palette_tint_accepts_tones_and_nudges_and_refuses_the_rest(self):
        for tone in palette_tints():
            self.assertTrue(is_palette_tint(tone), tone)
            self.assertTrue(is_palette_tint(nudged(tone, LIGHTNESS_NUDGE)), tone)
            self.assertTrue(is_palette_tint(nudged(tone, -LIGHTNESS_NUDGE)), tone)
        self.assertFalse(is_palette_tint((0.9, 1.05, 1.3)))
        self.assertFalse(is_palette_tint((0.65, 0.65, 0.65)))
        self.assertFalse(is_palette_tint(nudged(palette_tints()[4], 0.1)))
        self.assertFalse(is_palette_tint((0.0, 0.0, 0.0)))
        self.assertEqual(nearest_tone((0.7, 0.62, 0.49)), 5)


if __name__ == "__main__":
    unittest.main()
