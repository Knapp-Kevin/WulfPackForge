import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QComboBox, QLineEdit, QPushButton

import ui.mainWindow as mw
from tests.fixture_saves import realistic_player_data, realistic_root_save, write_fch
from tests.qt_support import dispose
from ui.recordTab import RecordTab

APP = QApplication.instance() or QApplication([])


def list_texts(widget):
    return [widget.item(i).text() for i in range(widget.count())]


class RecordTabTests(unittest.TestCase):
    def test_tab_shows_the_summary_and_never_writes(self):
        tab = RecordTab()
        player_data, root_save = realistic_player_data(), realistic_root_save()
        before = copy.deepcopy(player_data), copy.deepcopy(root_save)
        tab.load_data(player_data, root_save)
        self.assertEqual(tab.values["created"].text(), "2023-11-14 22:13 UTC")
        self.assertEqual(list_texts(tab.lists["trophies"]), ["Boar Trophy"])
        self.assertEqual(tab.groups["biomes"].title(), "Known biomes (3)")
        tab.save_changes()
        self.assertEqual((player_data, root_save), before)
        editable = (tab.findChildren(QLineEdit) + tab.findChildren(QAbstractSpinBox)
                    + tab.findChildren(QComboBox) + tab.findChildren(QPushButton))
        self.assertEqual(editable, [])
        dispose(tab)

    def test_the_record_tab_shows_the_achievement_risk_section(self):
        tab = RecordTab()
        flagged = realistic_root_save()
        flagged["used_cheats"] = True
        tab.load_data(realistic_player_data(), flagged)
        self.assertEqual(tab.groups["cheat_risk"].title(), "Achievement risk (4)")
        self.assertIn("set", list_texts(tab.lists["cheat_risk"])[0])
        tab.load_data(realistic_player_data(), realistic_root_save())
        lines = list_texts(tab.lists["cheat_risk"])
        self.assertEqual(len(lines), 4)
        self.assertFalse(any("safe" in line.lower() for line in lines))
        dispose(tab)

    def test_tab_clears_without_a_character(self):
        tab = RecordTab()
        tab.load_data(realistic_player_data(), realistic_root_save())
        tab.load_data(None, None)
        self.assertEqual(tab.lists["trophies"].count(), 0)
        self.assertEqual(tab.values["created"].text(), "Unknown")
        dispose(tab)

    def test_main_window_populates_the_record_tab(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(mw, "discover_character_records", return_value=[]), \
                patch("subscripts.workspace.default_workspace_root", return_value=Path(temp) / "workspace"):
            window = mw.MainWindow(startup_warning=False)
            titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
            self.assertIn("Record", titles)
            window.load_save_file(str(write_fch(Path(temp) / "hero.fch", realistic_root_save())))
            self.assertEqual(list_texts(window.record_tab.lists["worlds"]), ["WorldA"])
            dispose(window)


if __name__ == "__main__":
    unittest.main()
