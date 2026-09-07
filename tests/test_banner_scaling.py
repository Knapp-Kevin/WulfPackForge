import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from ui.mainWindow import BANNER_MAX_HEIGHT, BANNER_MIN_HEIGHT, MainWindow, banner_height_for
from tests.qt_support import dispose


APP = QApplication.instance() or QApplication([])
SOURCE = QSize(2048, 682)


class BannerScalingTests(unittest.TestCase):
    def test_height_follows_aspect_within_bounds(self):
        self.assertEqual(banner_height_for(600, SOURCE), 200)
        self.assertEqual(banner_height_for(3000, SOURCE), BANNER_MAX_HEIGHT)
        self.assertEqual(banner_height_for(100, SOURCE), BANNER_MIN_HEIGHT)

    def test_banner_follows_window_width_without_cropping(self):
        window = MainWindow(startup_warning=False)
        window.show()
        source = window._brand_pixmap.size()
        self.assertFalse(window._brand_pixmap.isNull())
        for width in (900, 1500):
            window.resize(width, 800)
            for _ in range(3):
                APP.processEvents()
            label = window.brand_banner
            pixmap = label.pixmap()
            logical_w = pixmap.width() / pixmap.devicePixelRatio()
            logical_h = pixmap.height() / pixmap.devicePixelRatio()
            self.assertLessEqual(round(logical_w), label.width(), width)
            self.assertEqual(label.height(), banner_height_for(label.width(), source), width)
            self.assertAlmostEqual(logical_w / logical_h, source.width() / source.height(), delta=0.02)
        dispose(window)


if __name__ == "__main__":
    unittest.main()
