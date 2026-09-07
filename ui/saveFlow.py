"""Filesystem helpers for the Save Changes flow; the policy stays in the main window."""
import os
import shutil
import tempfile
from typing import Iterable

EXTERNAL_CHANGE_MARKERS = ("changed after it was opened", "disappeared after it was opened")


def stage_candidate(working_path: str, destination: str) -> str:
    """Copy the verified working copy next to the destination so the final replace stays atomic."""
    with tempfile.NamedTemporaryFile(
        suffix=".fch", prefix=".wulfpack-forge-", dir=os.path.dirname(destination), delete=False
    ) as staged:
        staged_path = staged.name
    shutil.copy2(working_path, staged_path)
    return staged_path


def remove_quietly(paths: Iterable[str]) -> None:
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def mtime_or_none(path):
    try:
        return os.path.getmtime(path) if path else None
    except OSError:
        return None


def looks_like_external_change(message: str) -> bool:
    return any(marker in message for marker in EXTERNAL_CHANGE_MARKERS)
