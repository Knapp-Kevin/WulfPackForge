"""The UI-layer half of crash diagnostics: Qt messages, the environment banner, and the notice.

Everything here needs Qt, which is why it lives above ``subscripts/``: that layer carries no
PySide6 import, and the rule is enforced over the whole module tree.
"""
import logging
import platform
from functools import partial
from pathlib import Path
from typing import Optional, Sequence

import PySide6
from PySide6.QtCore import QUrl, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from subscripts import crashReports, silentErrors
from ui import messages
from ui.lifetime import modal

logger = logging.getLogger("qt")

QT_LEVELS = {
    QtMsgType.QtWarningMsg: logging.WARNING,
    QtMsgType.QtCriticalMsg: logging.ERROR,
    QtMsgType.QtFatalMsg: logging.CRITICAL,
}
SHOW_FOLDER = "Show folder"
NOTICE_TITLE = "Previous Session Ended Unexpectedly"

_previous_handler = None
_installed = False


def install_qt_message_handler() -> None:
    """Send Qt's own warnings and worse to the log; debug and info are dropped as routine."""
    global _previous_handler, _installed
    if _installed:
        return
    _previous_handler = qInstallMessageHandler(_qt_message)
    _installed = True


def detach_qt_message_handler() -> None:
    global _previous_handler, _installed
    if not _installed:
        return
    qInstallMessageHandler(_previous_handler)
    _previous_handler, _installed = None, False


def _qt_message(mode, _context, message) -> None:
    level = QT_LEVELS.get(mode)
    if level is not None:
        logger.log(level, "%s", message)


def environment_banner(report_path: Optional[Path]) -> str:
    """One line naming the build a crash report would belong to, and whether capture is armed."""
    armed = f"crash capture armed: {report_path}" if report_path else "crash capture NOT armed"
    return (f"Python {platform.python_version()}, PySide6 {PySide6.__version__}, "
            f"{platform.platform()}; {armed}")


def arm_diagnostics(root: Optional[Path] = None):
    """Prune, read earlier reports, arm capture, install every hook. Returns ``(reports, path)``.

    Pruning runs before the read: the reverse order could name a report in the notice that
    pruning had just removed.
    """
    crashReports.prune_reports(root)
    reports = crashReports.previous_reports(root)
    report_path = crashReports.install(root)
    silentErrors.install_hooks()
    install_qt_message_handler()
    return reports, report_path


def open_report_folder(report_path) -> None:
    """Open the directory holding the report in the desktop file manager."""
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(report_path).parent)))


def build_crash_notice(parent, report_path) -> QMessageBox:
    """Construct the notice without showing it, so its button can be exercised by a test."""
    box = QMessageBox(parent)
    box.setWindowTitle(NOTICE_TITLE)
    box.setIcon(QMessageBox.Information)
    box.setText(messages.previous_session_crashed(report_path))
    box.addButton(QMessageBox.Close)
    box.addButton(SHOW_FOLDER, QMessageBox.ActionRole).clicked.connect(
        partial(open_report_folder, report_path)
    )
    return box


def show_crash_notice(parent, reports: Sequence[Path]) -> None:
    """Name the newest crash report once, dispose the dialog, and mark the report as shown."""
    if not reports:
        return
    with modal(build_crash_notice(parent, reports[0])) as box:
        box.exec()
    crashReports.acknowledge(reports[0])
