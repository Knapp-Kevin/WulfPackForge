"""The editor's mode: full, or the vanilla-friendly appearance mode, remembered per install.

The mode is a courtesy for players of vanilla servers: with it on, the editor writes nothing
outside appearance and keeps colours and names within the server's expectations. It is not
enforcement; a player can switch it off, and the game file carries no trace of which mode wrote it.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MODE_FULL = "full"
MODE_VANILLA = "vanilla-friendly"
MODES = (MODE_FULL, MODE_VANILLA)
HAIR_CAP = 1.1  # the brightest hair or beard channel the mode writes
SETTINGS_NAME = "settings.json"
SCHEMA_VERSION = 1


def settings_path(workspace_root) -> Path:
    return Path(workspace_root) / SETTINGS_NAME


def load_mode(workspace_root) -> str:
    """The remembered mode; full when the file is missing, unreadable or names an unknown mode."""
    path = settings_path(workspace_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return MODE_FULL
    mode = data.get("mode") if isinstance(data, dict) else None
    return mode if mode in MODES else MODE_FULL


def save_mode(workspace_root, mode: str) -> None:
    """Remember ``mode``; a failure to write is logged, never raised, because a mode is a preference."""
    if mode not in MODES:
        raise ValueError(f"unknown editor mode: {mode!r}")
    path = settings_path(workspace_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema_version": SCHEMA_VERSION, "mode": mode}), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not remember the editor mode in %s: %s", path, exc)


def capitalised_words(name: str) -> bool:
    """The Jotunheim naming rule: every word of the name starts with a capital letter."""
    words = (name or "").split()
    return bool(words) and all(word[0].isupper() for word in words)
