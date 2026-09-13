import os
import unittest

from data.items import CATALOG_GAME_VERSION
from subscripts.saveHealth import (
    SAVE_STATE_COMPATIBILITY_UNVERIFIED,
    SAVE_STATE_NEEDS_ATTENTION,
    SAVE_STATE_VERIFIED,
    SUPPORTED_CHARACTER_SAVE_VERSIONS,
    build_save_health_report,
)


class SaveHealthTests(unittest.TestCase):
    def test_version_43_verified_save_is_writable(self):
        report = build_save_health_report(
            valid=True,
            version=43,
            source="Local",
            modified_at=1_700_000_000,
        )

        self.assertIn(43, SUPPORTED_CHARACTER_SAVE_VERSIONS)
        self.assertEqual(report.state, SAVE_STATE_VERIFIED)
        self.assertTrue(report.verification_ok)
        self.assertTrue(report.writable)
        self.assertEqual(report.catalog_game_version, CATALOG_GAME_VERSION)
        self.assertIn("checksum and structure verified", report.detail.lower())
        self.assertIn("protected workspace snapshot", report.detail.lower())

    def test_versions_40_to_43_and_46_are_writable_and_others_are_not(self):
        self.assertEqual(SUPPORTED_CHARACTER_SAVE_VERSIONS, frozenset({40, 41, 42, 43, 46}))

        v46 = build_save_health_report(valid=True, version=46, source="Local", modified_at=None)
        self.assertEqual(v46.state, SAVE_STATE_VERIFIED)
        self.assertTrue(v46.writable)

        writable = build_save_health_report(valid=True, version=41, source="Local", modified_at=None)
        self.assertEqual(writable.state, SAVE_STATE_VERIFIED)
        self.assertTrue(writable.writable)

        for version in (39, 44):
            report = build_save_health_report(valid=True, version=version, source="Local", modified_at=None)
            self.assertEqual(report.state, SAVE_STATE_COMPATIBILITY_UNVERIFIED, version)
            self.assertFalse(report.writable, version)

        gated = build_save_health_report(
            valid=True, version=41, source="Local", modified_at=None, payload_supported=False
        )
        self.assertEqual(gated.state, SAVE_STATE_COMPATIBILITY_UNVERIFIED)
        self.assertFalse(gated.writable)

    def test_unknown_save_version_is_inspectable_but_not_writable(self):
        report = build_save_health_report(
            valid=True,
            version=44,
            source="Active save (Valheim, Steam Cloud folder)",
            modified_at=1_700_000_000,
        )

        self.assertEqual(report.state, SAVE_STATE_COMPATIBILITY_UNVERIFIED)
        self.assertEqual(report.source, "Active save (Valheim, Steam Cloud folder)")
        self.assertTrue(report.verification_ok)
        self.assertFalse(report.writable)
        self.assertIn("save version 44", report.detail.lower())
        self.assertIn("disabled", report.detail.lower())

    def test_unsupported_payload_versions_are_inspectable_but_not_writable(self):
        report = build_save_health_report(
            valid=True,
            version=43,
            source="Local",
            modified_at=1_700_000_000,
            payload_supported=False,
        )

        self.assertEqual(report.state, SAVE_STATE_COMPATIBILITY_UNVERIFIED)
        self.assertTrue(report.verification_ok)
        self.assertFalse(report.writable)
        self.assertIn("player data", report.detail.lower())

    def test_failed_verification_needs_attention_and_is_not_writable(self):
        report = build_save_health_report(
            valid=False,
            version=None,
            source="Manual file",
            modified_at=None,
            error="checksum mismatch",
        )

        self.assertEqual(report.state, SAVE_STATE_NEEDS_ATTENTION)
        self.assertFalse(report.verification_ok)
        self.assertFalse(report.writable)
        self.assertIn("checksum mismatch", report.detail)

    def test_external_source_change_needs_attention_without_calling_save_corrupt(self):
        report = build_save_health_report(
            valid=True,
            version=43,
            source="Active save (Valheim, Steam Cloud folder)",
            modified_at=1_700_000_000,
            source_changed=True,
        )

        self.assertEqual(report.state, SAVE_STATE_NEEDS_ATTENTION)
        self.assertEqual(report.source, "Active save (Valheim, Steam Cloud folder)")
        self.assertTrue(report.verification_ok)
        self.assertFalse(report.writable)
        self.assertTrue(report.source_changed)
        self.assertIn("changed outside Wulfpack Forge", report.detail)
        self.assertIn("reload", report.detail.lower())

    def test_backup_path_is_presented_by_filename(self):
        report = build_save_health_report(
            valid=True,
            version=43,
            source="Local",
            modified_at=1_700_000_000,
            backup_path=os.path.join("tmp", "Frostwulf.fch.20260906T003000Z.bak"),
        )

        self.assertEqual(report.backup_label, "Frostwulf.fch.20260906T003000Z.bak")
        self.assertIn("2023-11", report.modified_label)


if __name__ == "__main__":
    unittest.main()
