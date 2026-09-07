import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from tests.qt_support import QtTestCase

from PySide6.QtWidgets import QApplication

from subscripts.saveHealth import build_save_health_report
from ui.saveStatusWidget import SaveStatusWidget


_app = QApplication.instance() or QApplication([])


class SaveStatusWidgetTests(QtTestCase):
    def test_verified_report_renders_compact_metadata(self):
        widget = SaveStatusWidget()
        report = build_save_health_report(
            valid=True,
            version=43,
            source="Steam Cloud (local copy)",
            modified_at=1_700_000_000,
            backup_path="/tmp/frostwulf.fch.20260906.bak",
        )

        widget.set_report(report)

        self.assertEqual(widget.state_label.text(), "Verified")
        self.assertIn("Save v43", widget.meta_label.text())
        self.assertIn("Steam Cloud (local copy)", widget.meta_label.text())
        self.assertIn("Catalog: Valheim", widget.meta_label.text())
        self.assertIn("Backup: frostwulf.fch.20260906.bak", widget.meta_label.text())
        self.assertIn("protected workspace snapshot", widget.detail_label.text())
        self.assertIn("#c4d8df", widget.meta_label.styleSheet())
        self.assertIn("#a9c1ca", widget.detail_label.styleSheet())

    def test_unverified_compatibility_is_visible_without_claiming_corruption(self):
        widget = SaveStatusWidget()
        report = build_save_health_report(
            valid=True,
            version=44,
            source="Manual file",
            modified_at=None,
        )

        widget.set_report(report)

        self.assertEqual(widget.state_label.text(), "Compatibility unverified")
        self.assertIn("Save v44", widget.meta_label.text())
        self.assertIn("Save Changes is disabled", widget.detail_label.text())

    def test_external_source_change_renders_needs_attention(self):
        widget = SaveStatusWidget()
        report = build_save_health_report(
            valid=True,
            version=43,
            source="Steam Cloud (local copy)",
            modified_at=1_700_000_000,
            source_changed=True,
        )

        widget.set_report(report)

        self.assertEqual(widget.state_label.text(), "Needs attention")
        self.assertIn("Steam Cloud (local copy)", widget.meta_label.text())
        self.assertIn("changed outside Wulfpack Forge", widget.detail_label.text())

    def test_clear_returns_to_neutral_state(self):
        widget = SaveStatusWidget()
        widget.clear()

        self.assertEqual(widget.state_label.text(), "No character loaded")
        self.assertIn("Open a character", widget.detail_label.text())


if __name__ == "__main__":
    unittest.main()
