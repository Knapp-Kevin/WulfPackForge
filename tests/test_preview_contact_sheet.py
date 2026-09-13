import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from tools.preview_contact_sheet import main, render_sheet

APP = QApplication.instance() or QApplication([])


class PreviewContactSheetTests(unittest.TestCase):
    def test_render_sheet_lays_hairs_out_in_a_grid(self):
        image = render_sheet("Beard3", ["Hair1", "Hair7", "Hair12"], 64)
        self.assertEqual((image.width(), image.height()), (192, 64))
        for column in range(3):
            painted = any(image.pixelColor(column * 64 + x, y).alpha() > 200
                          for x in range(0, 64, 4) for y in range(0, 64, 4))
            self.assertTrue(painted, f"column {column} is empty")

    def test_main_writes_one_png_per_requested_beard(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["--out", tmp, "--beard", "Beard3", "--size", "32"]), 0)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["sheet-Beard3.png"])


if __name__ == "__main__":
    unittest.main()
