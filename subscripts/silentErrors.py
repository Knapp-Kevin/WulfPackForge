"""Log the failures Python otherwise discards: unraisable exceptions and dead worker threads.

``sys.excepthook`` covers exceptions that reach the top of the main thread, including those
raised inside a Qt slot. It does not cover an exception in ``__del__`` or during garbage
collection, which the interpreter reports as *unraisable* and then swallows, nor one that
kills a worker thread. Both are silent today, and the app runs pool workers for character
discovery, icon extraction, and mod scanning.
"""
import logging
import sys
import threading

logger = logging.getLogger(__name__)

_previous = {}


def install_hooks() -> None:
    """Route unraisable exceptions and thread failures into the log."""
    if _previous:
        return
    _previous["unraisable"] = sys.unraisablehook
    _previous["thread"] = threading.excepthook
    sys.unraisablehook = _unraisable
    threading.excepthook = _thread_failed


def detach_hooks() -> None:
    """Restore the interpreter's own hooks (tests, or before switching roots)."""
    if not _previous:
        return
    sys.unraisablehook = _previous["unraisable"]
    threading.excepthook = _previous["thread"]
    _previous.clear()


def _unraisable(args) -> None:
    logger.error(
        "Unraisable %s in %r", args.exc_type.__name__, args.object,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def _thread_failed(args) -> None:
    if args.exc_type is SystemExit:
        return
    name = args.thread.name if args.thread is not None else "unknown"
    logger.error(
        "Unhandled %s in thread %s", args.exc_type.__name__, name,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )
