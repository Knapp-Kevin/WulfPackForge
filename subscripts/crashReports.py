"""Capture native faults the Python excepthook never sees, so a crash leaves a stack.

An access violation inside Qt or shiboken kills the process without raising a Python
exception: ``sys.excepthook`` never runs and the rotating log keeps only its startup line.
``faulthandler`` writes the interpreter's own stack for every live thread straight to a file
descriptor, which still works while the process is dying. Nothing here may raise on the
startup path, and nothing is parsed out of a report filename.
"""
import faulthandler
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from subscripts.logSetup import log_path

logger = logging.getLogger(__name__)

REPORT_PREFIX = "crash-"
REPORT_SUFFIX = ".log"
REPORT_GLOB = f"{REPORT_PREFIX}*{REPORT_SUFFIX}"
REPORT_RETENTION = 5  # non-empty reports kept
EMPTY_REPORT_CAP = 5  # empty reports kept regardless of age
EMPTY_REPORT_MAX_AGE = 86400  # an empty report younger than this is always kept (seconds)
STAMP = "%Y%m%dT%H%M%SZ"  # colons are not legal in a Windows filename

_handle = None
_path: Optional[Path] = None


def reports_dir(root: Optional[Path] = None) -> Path:
    """The directory that already holds the rotating log, so there is one place to look."""
    return log_path(root).parent


def _report_name() -> str:
    return f"{REPORT_PREFIX}{datetime.now(timezone.utc).strftime(STAMP)}-{os.getpid()}{REPORT_SUFFIX}"


def _create(path: Path) -> Tuple[Path, object]:
    """Exclusive create, so a name collision can never truncate an existing report."""
    candidate, counter = path, 1
    while True:
        try:
            descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
            counter += 1
            continue
        return candidate, os.fdopen(descriptor, "wb", buffering=0)


def install(root: Optional[Path] = None) -> Optional[Path]:
    """Arm fault capture; return the report path, or ``None`` when the location is unusable."""
    global _handle, _path
    if _handle is not None:
        return _path
    directory = reports_dir(root)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path, handle = _create(directory / _report_name())
    except OSError as exc:
        logger.error("Crash capture is NOT armed; could not open a report in %s: %s", directory, exc)
        return None
    _path, _handle = path, handle
    faulthandler.enable(file=handle, all_threads=True)
    return _path


def release() -> Optional[Path]:
    """Disarm and drop an empty report. Safe to call when capture was never armed."""
    global _handle, _path
    handle, path = _handle, _path
    _handle, _path = None, None
    if handle is None:
        return None
    faulthandler.disable()
    try:
        handle.close()
        if path.stat().st_size == 0:
            path.unlink()
            return None
    except OSError:
        return None
    return path


def _scan(root: Optional[Path]) -> List[Tuple[Path, int, float]]:
    """``(path, size, mtime)`` per report, newest first; empty when the directory is unreadable."""
    found = []
    try:
        for path in reports_dir(root).glob(REPORT_GLOB):
            try:
                status = path.stat()
            except OSError:
                continue
            if path.is_file():
                found.append((path, status.st_size, status.st_mtime))
    except OSError as exc:
        logger.warning("Could not read crash reports: %s", exc)
        return []
    found.sort(key=lambda entry: entry[2], reverse=True)
    return found


def previous_reports(root: Optional[Path] = None) -> List[Path]:
    """Reports an earlier run actually wrote to, newest first. Never raises."""
    return [path for path, size, _ in _scan(root) if size > 0 and path != _path]


def prune_reports(root: Optional[Path] = None, keep: int = REPORT_RETENTION) -> List[Path]:
    """Drop over-retention reports and long-stale empty ones. Never raises."""
    scanned = _scan(root)
    filled = [path for path, size, _ in scanned if size > 0]
    empty = [(path, mtime) for path, size, mtime in scanned if size == 0]
    cutoff = time.time() - EMPTY_REPORT_MAX_AGE
    stale = [path for path, mtime in empty[EMPTY_REPORT_CAP:] if mtime < cutoff]
    return _remove(filled[keep:] + stale)


def _remove(paths: List[Path]) -> List[Path]:
    removed = []
    for path in paths:
        if path == _path:
            continue
        try:
            path.unlink()
            removed.append(path)
            logger.info("Pruned crash report %s", path)
        except OSError as exc:
            logger.warning("Could not prune %s: %s", path, exc)
    return removed
