"""Deterministic teardown for Qt widgets created in tests.

unittest drops TestCase instances as it goes, so a window kept on ``self`` is otherwise freed by the
cyclic garbage collector at an arbitrary later point, possibly in the middle of another test's Qt
allocation burst. Deleting through Qt's own deferred-delete path on the UI thread, then collecting,
removes that source of use-after-free crashes.
"""
import gc

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


def dispose(widget) -> None:
    if widget is None:
        return
    widget.close()
    widget.deleteLater()
    app = QApplication.instance()
    if app is not None:
        app.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
    gc.collect()
