"""Failures leave a log trace as well as a dialog, and cleanup never fails silently."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import ui.mainWindow as mw
from subscripts.saveFlow import remove_quietly


APP = QApplication.instance() or QApplication([])


class QuietMessageBox:
    calls = []

    @classmethod
    def critical(cls, *args, **kwargs):
        cls.calls.append(args[1])

    @classmethod
    def warning(cls, *args, **kwargs):
        cls.calls.append(args[1])


class HardeningTests(unittest.TestCase):
    def test_load_failure_is_logged(self):
        QuietMessageBox.calls = []
        with tempfile.TemporaryDirectory() as temp:
            garbage = Path(temp) / "broken.fch"
            garbage.write_bytes(b"not a save at all")
            with patch.object(mw, "discover_character_records", return_value=[]), \
                    patch.object(mw, "QMessageBox", QuietMessageBox), \
                    self.assertLogs("ui.mainWindow", level="ERROR") as logs:
                window = mw.MainWindow(startup_warning=False)
                window.load_save_file(str(garbage))
                window.close()
        self.assertIn("Character Could Not Be Opened", QuietMessageBox.calls)
        self.assertTrue(any("broken.fch" in line for line in logs.output), logs.output)

    def test_cleanup_failure_is_logged(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertLogs("subscripts.saveFlow", level="WARNING") as logs:
                remove_quietly([temp])  # a directory: os.remove refuses, and we must not raise
            self.assertTrue(Path(temp).exists())
        self.assertTrue(any("temporary file" in line.lower() for line in logs.output), logs.output)


if __name__ == "__main__":
    unittest.main()
