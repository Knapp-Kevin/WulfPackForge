"""The startup wiring itself: the finally release, the notice call, and the banner.

Audit iteration 2 found nothing in the suite imported ``main``, so every promise about
``main()`` was asserted by the plan and verified by nothing.
"""
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import main as main_module
from subscripts import characterRecords, logSetup
from subscripts.crashReports import REPORT_GLOB, reports_dir
from subscripts.logSetup import detach_logging
from tests.qt_support import dispose_all

app = QApplication.instance() or QApplication([])


def _reuse_application(argv):
    """Qt permits one QApplication per process; the suite already owns it."""
    return QApplication.instance() or QApplication(argv)


class MainStartupTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        workspace = self.root / "WulfpackForge"
        self.logs = workspace / "logs"
        # Patch the function on each module that resolves it, not the environment: LOCALAPPDATA
        # and XDG_DATA_HOME steer default_workspace_root on Windows and Linux but not on macOS,
        # where it returns ~/Library/Application Support unconditionally. Instrumenting a real
        # --smoke-test run shows exactly these three modules resolve it on this path.
        self._patches = [patch.object(module, "default_workspace_root", return_value=workspace)
                         for module in (logSetup, characterRecords, main_module)]
        for started in self._patches:
            started.start()
        self._app = patch.object(main_module, "QApplication", _reuse_application)
        self._app.start()

    def tearDown(self):
        self._app.stop()
        for started in self._patches:
            started.stop()
        detach_logging()
        dispose_all()
        self._temp.cleanup()

    def _run(self, *argv):
        with patch.object(main_module.sys, "argv", ["main.py", *argv]):
            return main_module.main()

    def _reports(self):
        directory = reports_dir()
        return sorted(directory.glob(REPORT_GLOB)) if directory.is_dir() else []

    def _plant_report(self) -> Path:
        self.logs.mkdir(parents=True, exist_ok=True)
        report = self.logs / "crash-20260908T151056Z-4242.log"
        report.write_text("Windows fatal exception: access violation\n", encoding="utf-8")
        return report

    def test_a_smoke_run_leaves_no_report(self):
        with patch.object(main_module, "show_crash_notice"):
            self.assertEqual(self._run("--smoke-test"), 0)
        self.assertEqual(self._reports(), [], "a zero-byte report leaked from the smoke path")

    def test_a_smoke_run_shows_no_crash_notice(self):
        self._plant_report()
        with patch.object(main_module, "show_crash_notice") as notice:
            self.assertEqual(self._run("--smoke-test"), 0)
        notice.assert_not_called()

    def test_a_normal_run_shows_the_notice_once_with_the_window_as_parent(self):
        report = self._plant_report()
        with patch.object(QApplication, "exec", return_value=0), \
                patch.object(main_module, "show_crash_notice") as notice:
            self.assertEqual(self._run(), 0)
        notice.assert_called_once()
        window, reports = notice.call_args[0]
        self.assertIsInstance(window, main_module.MainWindow)
        self.assertEqual(list(reports), [report])

    def test_the_startup_banner_is_logged(self):
        with self.assertLogs(main_module.__name__, level=logging.INFO) as caught, \
                patch.object(main_module, "show_crash_notice"):
            self._run("--smoke-test")
        banner = "\n".join(caught.output)
        self.assertIn("PySide6", banner)
        self.assertIn("crash capture armed", banner)

    def test_the_banner_says_so_when_capture_could_not_be_armed(self):
        self.logs.parent.mkdir(parents=True, exist_ok=True)
        self.logs.write_text("not a directory", encoding="utf-8")  # blocks the logs dir
        with self.assertLogs(main_module.__name__, level=logging.INFO) as caught, \
                patch.object(main_module, "show_crash_notice"):
            self._run("--smoke-test")
        self.assertIn("crash capture NOT armed", "\n".join(caught.output))


if __name__ == "__main__":
    unittest.main()
