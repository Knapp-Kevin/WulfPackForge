"""Cosmetic edits must not disturb any achievement-sensitive character state."""
import os
import shutil
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from subscripts.valheim_detection import ScanState, ValheimScan
from tests.fixture_saves import realistic_root_save, write_fch
from tests.qt_support import dispose
from tools.compare_saves import compare
from ui import mainWindow as mw

APP = QApplication.instance() or QApplication([])


def _fields(differences):
    return sorted({line.split(":")[0] for line in differences})


class AchievementCosmeticIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.save_dir = root / "characters_local"
        self.save_dir.mkdir()
        self.source = write_fch(self.save_dir / "hero.fch", realistic_root_save())
        self.before = root / "before.fch"
        shutil.copy(self.source, self.before)
        self.stack = ExitStack()
        self.stack.enter_context(patch("subscripts.workspace.default_workspace_root", return_value=root / "workspace"))
        self.stack.enter_context(patch.object(mw, "scan_valheim", side_effect=lambda: ValheimScan(state=ScanState.NOT_RUNNING)))
        self.stack.enter_context(patch.object(mw, "discover_character_records", return_value=[]))
        self.window = mw.MainWindow(startup_warning=False)
        self.window.load_save_file(str(self.source))

    def tearDown(self):
        dispose(self.window)
        self.window = None
        self.stack.close()
        self.temp.cleanup()

    def _save_and_fields(self):
        self.window.save_save_file()
        return _fields(compare(str(self.before), str(self.source)))

    def test_hair_color_changes_only_hair_color(self):
        tab = self.window.appearance_tab
        tab.current_hair_rgb = [0.21, 0.42, 0.84]
        tab._sync_hdr_spins()
        self.assertEqual(self._save_and_fields(), ["payload.hair_color"])

    def test_hair_style_changes_only_hair_style(self):
        tab = self.window.appearance_tab
        original = tab.hair_combo.currentData()
        index = next(i for i in range(tab.hair_combo.count()) if tab.hair_combo.itemData(i) != original)
        tab.hair_combo.setCurrentIndex(index)
        self.assertEqual(self._save_and_fields(), ["payload.hair"])

    def test_beard_style_changes_only_beard_style(self):
        tab = self.window.appearance_tab
        original = tab.beard_combo.currentData()
        index = next(i for i in range(tab.beard_combo.count()) if tab.beard_combo.itemData(i) != original)
        tab.beard_combo.setCurrentIndex(index)
        self.assertEqual(self._save_and_fields(), ["payload.beard"])

    def test_cosmetic_save_preserves_all_cheat_evidence(self):
        before_flag = self.window.root_save["used_cheats"]
        before_flags = [item["_wire"]["cheat_flags"] for item in self.window.player_data["inventory"]]
        self.window.appearance_tab.current_hair_rgb = [0.31, 0.52, 0.73]
        self.window.save_save_file()
        self.assertEqual(self.window.root_save["used_cheats"], before_flag)
        after_flags = [item["_wire"]["cheat_flags"] for item in self.window.player_data["inventory"]]
        self.assertEqual(after_flags, before_flags)
        self.assertEqual(_fields(compare(str(self.before), str(self.source))), ["payload.hair_color"])


if __name__ == "__main__":
    unittest.main()
