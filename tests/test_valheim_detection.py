import unittest
from unittest.mock import patch

import psutil

from subscripts import valheim_detection as vd


class FakeProc:
    def __init__(self, name):
        self.info = {"pid": 1, "name": name, "exe": None}


def _patched(processes):
    return patch.object(vd.psutil, "process_iter", return_value=processes)


class ValheimDetectionTests(unittest.TestCase):
    def test_unreadable_name_before_valheim_still_reports_running(self):
        with _patched([FakeProc(None), FakeProc("valheim.exe")]):
            scan = vd.scan_valheim()
        self.assertEqual(scan.state, vd.ScanState.RUNNING)
        self.assertEqual(scan.process["name"], "valheim.exe")

    def test_unreadable_name_alone_is_inconclusive(self):
        with _patched([FakeProc(None), FakeProc("explorer.exe")]):
            scan = vd.scan_valheim()
        self.assertEqual(scan.state, vd.ScanState.INCONCLUSIVE)
        self.assertIn("1 process", scan.detail)

    def test_clean_scan_is_not_running(self):
        with _patched([FakeProc("explorer.exe"), FakeProc("steam.exe")]):
            scan = vd.scan_valheim()
        self.assertEqual(scan.state, vd.ScanState.NOT_RUNNING)

    def test_psutil_failure_is_inconclusive(self):
        with patch.object(vd.psutil, "process_iter", side_effect=psutil.Error("boom")):
            scan = vd.scan_valheim()
        self.assertEqual(scan.state, vd.ScanState.INCONCLUSIVE)
        self.assertIn("boom", scan.detail)

    def test_is_valheim_running_is_true_only_for_running(self):
        with _patched([FakeProc(None)]):
            self.assertFalse(vd.is_valheim_running())
        with _patched([FakeProc("valheim.exe")]):
            self.assertTrue(vd.is_valheim_running())


if __name__ == "__main__":
    unittest.main()
