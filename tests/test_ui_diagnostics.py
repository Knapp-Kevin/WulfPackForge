import logging
import platform
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import PySide6
from PySide6.QtCore import qDebug, qWarning
from PySide6.QtWidgets import QApplication, QMessageBox

from tests.qt_support import QtTestCase, dispose
from ui import diagnostics
from ui.diagnostics import (
    SHOW_FOLDER,
    build_crash_notice,
    detach_qt_message_handler,
    environment_banner,
    install_qt_message_handler,
    open_report_folder,
    show_crash_notice,
)
from ui.messages import previous_session_crashed

app = QApplication.instance() or QApplication([])
# Absolute on every platform: two tests round-trip this through QUrl.fromLocalFile,
# which a Windows-shaped literal cannot survive on macOS or Linux.
REPORT = Path(tempfile.gettempdir(), "WulfpackForge", "logs", "crash-20260908T151056Z-42.log")


class RecordingMessageBox:
    """Counts constructions; a replaced dialog has no button, so the button has its own tests."""
    built = []
    Information = QMessageBox.Information
    Close = QMessageBox.Close
    ActionRole = QMessageBox.ActionRole

    def __init__(self, *args, **kwargs):
        RecordingMessageBox.built.append(self)
        self.text = ""

    def setWindowTitle(self, *a): pass
    def setIcon(self, *a): pass
    def setText(self, text): self.text = text
    def addButton(self, *a): return self
    def exec(self): return 0
    def close(self): self.closed = True
    def deleteLater(self): self.deleted = True

    clicked = property(lambda self: self)

    def connect(self, *a): pass


class QtMessageHandlerTests(unittest.TestCase):
    def tearDown(self):
        detach_qt_message_handler()

    def test_qt_warnings_reach_the_log(self):
        install_qt_message_handler()
        with self.assertLogs("qt", level=logging.WARNING) as caught:
            qWarning("paint device returned engine == 0")
        self.assertIn("paint device returned engine == 0", "\n".join(caught.output))

    def test_qt_debug_messages_are_dropped(self):
        install_qt_message_handler()
        logging.getLogger("qt").warning("anchor")
        with self.assertLogs("qt", level=logging.WARNING) as caught:
            logging.getLogger("qt").warning("anchor")
            qDebug("routine chatter nobody needs")
        self.assertNotIn("routine chatter", "\n".join(caught.output))

    def test_detach_restores_the_qt_handler(self):
        install_qt_message_handler()
        detach_qt_message_handler()
        logging.getLogger("qt").warning("anchor")
        with self.assertLogs("qt", level=logging.WARNING) as caught:
            logging.getLogger("qt").warning("anchor")
            qWarning("this must not be captured any more")
        self.assertNotIn("must not be captured", "\n".join(caught.output))


class EnvironmentBannerTests(unittest.TestCase):
    def test_environment_banner_reports_the_running_versions(self):
        banner = environment_banner(REPORT)
        self.assertIn(PySide6.__version__, banner)
        self.assertIn(platform.python_version(), banner)
        self.assertIn(platform.platform(), banner)

    def test_environment_banner_states_whether_capture_is_armed(self):
        self.assertIn(str(REPORT), environment_banner(REPORT))
        self.assertIn("NOT armed", environment_banner(None))


class CrashNoticeTests(QtTestCase):
    def test_notice_text_names_the_report_and_says_what_it_contains(self):
        text = previous_session_crashed(REPORT)
        self.assertIn(str(REPORT), text)
        self.assertIn("ended unexpectedly", text)
        self.assertIn("character files were not affected", text)
        self.assertIn("account name", text)  # what a shared report discloses

    def test_show_crash_notice_displays_the_newest_report_once(self):
        older = REPORT.with_name("crash-20260907T090000Z-7.log")
        RecordingMessageBox.built = []
        with patch.object(diagnostics, "QMessageBox", RecordingMessageBox):
            show_crash_notice(None, [REPORT, older])
        self.assertEqual(len(RecordingMessageBox.built), 1)
        self.assertIn(str(REPORT), RecordingMessageBox.built[0].text)
        self.assertNotIn(str(older), RecordingMessageBox.built[0].text)

    def test_show_crash_notice_does_nothing_without_reports(self):
        RecordingMessageBox.built = []
        with patch.object(diagnostics, "QMessageBox", RecordingMessageBox):
            show_crash_notice(None, [])
        self.assertEqual(RecordingMessageBox.built, [])

    def test_the_notice_dialog_is_disposed(self):
        RecordingMessageBox.built = []
        with patch.object(diagnostics, "QMessageBox", RecordingMessageBox):
            show_crash_notice(None, [REPORT])
        self.assertTrue(getattr(RecordingMessageBox.built[0], "deleted", False))

    def test_show_crash_notice_acknowledges_the_report_it_showed(self):
        older = REPORT.with_name("crash-20260907T090000Z-7.log")
        RecordingMessageBox.built = []
        with patch.object(diagnostics, "QMessageBox", RecordingMessageBox), \
                patch.object(diagnostics.crashReports, "acknowledge") as acknowledged:
            show_crash_notice(None, [REPORT, older])
        acknowledged.assert_called_once_with(REPORT)

    def test_show_folder_opens_the_report_directory(self):
        with patch.object(diagnostics.QDesktopServices, "openUrl") as opened:
            open_report_folder(REPORT)
        opened.assert_called_once()
        self.assertEqual(Path(opened.call_args[0][0].toLocalFile()), REPORT.parent)

    def test_the_show_folder_button_is_connected_to_that_handler(self):
        box = build_crash_notice(None, REPORT)
        try:
            button = next(b for b in box.buttons() if b.text().replace("&", "") == SHOW_FOLDER)
            with patch.object(diagnostics.QDesktopServices, "openUrl") as opened:
                button.clicked.emit()
            opened.assert_called_once()
            self.assertEqual(Path(opened.call_args[0][0].toLocalFile()), REPORT.parent)
        finally:
            dispose(box)


if __name__ == "__main__":
    unittest.main()
