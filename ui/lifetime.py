"""Own a modal dialog for the length of a block, so it is destroyed at a point we choose.

A dialog left to Python is destroyed whenever its last reference goes, or - if it is caught in
a reference cycle - whenever the cyclic collector next runs, which can be in the middle of an
unrelated Qt operation. ``modal`` makes the point of destruction the end of the block, on every
exit path: normal fall-through, an early ``return``, or an exception.
"""
from contextlib import contextmanager

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


def dispose(widget) -> None:
    """Close a widget and destroy it now. Never raises.

    ``modal`` calls this from a ``finally``, so a raise here would replace whatever exception was
    already travelling with a misleading one. It therefore tolerates a widget whose C++ object is
    already gone, and anything that is not a widget at all, such as a test double standing in for
    a dialog.

    Deliberately does not collect: ``gc.collect()`` belongs to the test helper, because a collect
    here would hide whether a widget was released by reference counting or by the collector.
    """
    if widget is None:
        return
    try:
        widget.close()
        widget.deleteLater()
    except RuntimeError:
        return  # the C++ object was already destroyed
    except AttributeError:
        return  # not a widget: a test double standing in for a dialog
    app = QApplication.instance()
    if app is not None:
        app.sendPostedEvents(None, QEvent.DeferredDelete)


@contextmanager
def modal(dialog):
    """Yield ``dialog`` for the block, then dispose it however the block ends."""
    try:
        yield dialog
    finally:
        dispose(dialog)
