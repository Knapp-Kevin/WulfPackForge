"""Deterministic teardown for Qt widgets created in tests.

unittest drops TestCase instances as it goes, so a window kept on ``self`` is otherwise freed by the
cyclic garbage collector at an arbitrary later point, possibly in the middle of another test's Qt
allocation burst. Deleting through Qt's own deferred-delete path on the UI thread, then collecting,
removes that source of use-after-free crashes.
"""
import gc
import unittest

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


def dispose_all() -> None:
    """Dispose every top-level widget the current test left behind (parentless widgets are top-level)."""
    app = QApplication.instance()
    if app is None:
        return
    for widget in app.topLevelWidgets():
        shutdown = getattr(widget, "shutdown", None)  # the character picker stops its scan thread
        if callable(shutdown):
            shutdown()
        widget.close()
        widget.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    gc.collect()


class QtTestCase(unittest.TestCase):
    """Base class for tests that build widgets: tears every widget down deterministically after each test."""

    def tearDown(self):
        dispose_all()
        super().tearDown()
