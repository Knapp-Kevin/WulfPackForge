import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import ui.modScanDialog as dlg
import ui.skillsTab as skills
from subscripts.modOverride import reset_overrides
from subscripts.modProfiles import ModProfile
from subscripts.modScan import ScanReport, write_catalog
from tests.qt_support import QtTestCase

APP = QApplication.instance() or QApplication([])


def _fake_scan(profile, out_dir, progress=None):
    if progress:
        progress("Reading plugin strings", 1, 1)
    write_catalog(out_dir, profile, {2143840399: "Sailing"}, {})
    return ScanReport(profile.name, str(Path(out_dir) / "catalog.json"), dll_count=1, identifier_count=1)


class ModScanDialogTests(QtTestCase):
    def test_dialog_scans_the_chosen_profile_and_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = ModProfile("Test", Path(temp) / "BepInEx")
            (profile.plugins_dir).mkdir(parents=True)
            with patch.object(dlg, "scan_profile", _fake_scan):
                dialog = dlg.ModScanDialog(profiles=[profile], out_dir=Path(temp) / "mods")
                reports = []
                dialog.scanned.connect(reports.append)
                dialog.start()
                for _ in range(200):
                    APP.processEvents()
                    if reports:
                        break
                    dialog._check()
            self.assertEqual(len(reports), 1)
            self.assertIn("Scanned 1 plugins", dialog.status.text())
            self.assertTrue((Path(temp) / "mods" / "catalog.json").is_file())
            dialog.shutdown()

    def test_dialog_without_profiles_cannot_scan(self):
        dialog = dlg.ModScanDialog(profiles=[], out_dir="unused")
        self.assertFalse(dialog.btn_scan.isEnabled())

    def test_skills_tab_relabels_rows_after_a_scan(self):
        reset_overrides()
        tab = skills.SkillsTab()
        tab.load_data({"skills": [{"id": 2143840399, "level": 3.0, "xp": 0.0}, {"id": 1, "level": 1.0, "xp": 0.0}]})
        self.assertEqual(tab.table.item(0, 0).text(), "Unknown (2143840399)")
        with patch.object(skills, "apply_overrides"), patch.object(skills, "skill_label", side_effect=lambda i: {2143840399: "Sailing", 1: "Swords"}[i]):
            tab._mods_scanned(ScanReport("Test", "x"))
        self.assertEqual(tab.table.item(0, 0).text(), "Sailing")
        self.assertEqual(tab.table.item(1, 0).text(), "Swords")
        self.assertTrue(tab.btn_mods.isEnabled())


if __name__ == "__main__":
    unittest.main()
