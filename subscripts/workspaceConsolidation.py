"""Merge workspace directories keyed on the old identity pair into the player-id directory.

Until phase 45 a workspace directory was named from ``(player_id, date_created_unix)``. Valheim 1.0
rewrites the creation stamp on every load, so one character could own several directories. This
runs once per launch, before the window exists: every file is moved into the directory named by
``player_id`` alone and nothing is deleted. A directory whose metadata cannot be read is left in
place and logged; nothing here may end startup.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from subscripts.workspace import _character_id

logger = logging.getLogger(__name__)

SUBFOLDERS = ("source", "working", "backups")
WORKING_NAME = "character.fch"
METADATA_NAME = "metadata.json"


def consolidate_workspaces(workspace_root: Path) -> List[Tuple[Path, Path]]:
    """Move each old-pair directory into its identity directory; ``(old, new)`` per move."""
    active = Path(workspace_root) / "characters" / "active"
    if not active.is_dir():
        return []
    moved: List[Tuple[Path, Path]] = []
    for old in sorted(path for path in active.iterdir() if path.is_dir()):
        identity = _read_identity(old)
        if identity is None or old.name == _character_id(*identity):
            continue
        target = active / _character_id(*identity)
        try:
            _move_directory(old, target)
        except (OSError, ValueError) as exc:
            logger.warning("Could not consolidate %s into %s: %s", old, target, exc)
            continue
        logger.info("Consolidated workspace %s into %s", old, target)
        moved.append((old, target))
    return moved


def _read_identity(directory: Path) -> Optional[Tuple[str, int]]:
    """``(character_name, player_id)`` from the directory's metadata, or ``None`` with a warning."""
    try:
        data = json.loads((directory / METADATA_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Skipping %s: metadata unreadable (%s)", directory, exc)
        return None
    player_id = data.get("player_id") if isinstance(data, dict) else None
    if not isinstance(player_id, int) or isinstance(player_id, bool):
        logger.warning("Skipping %s: metadata carries no player id", directory)
        return None
    return str(data.get("character_name") or directory.name), player_id


def _move_directory(old: Path, target: Path) -> None:
    renames: Dict[str, str] = {}
    for sub in SUBFOLDERS:
        (target / sub).mkdir(parents=True, exist_ok=True)
    _place_working_copy(old / "working" / WORKING_NAME, target, renames)
    for sub in ("source", "backups"):
        for file in _files(old / sub):
            _move(file, target / sub / file.name, renames)
    metadata = old / METADATA_NAME
    if metadata.is_file() and (target / METADATA_NAME).is_file():
        _move(metadata, target / "backups" / f"metadata.{_stamp()}.superseded.json", renames)
    elif metadata.is_file():
        _retarget_metadata(metadata, old, target, renames)
        _move(metadata, target / METADATA_NAME, renames)
    for stray in _files(old) + [file for sub in SUBFOLDERS for file in _files(old / sub)]:
        _move(stray, target / "backups" / stray.name, renames)
    for sub in SUBFOLDERS:
        if (old / sub).is_dir():
            (old / sub).rmdir()
    old.rmdir()


def _place_working_copy(candidate: Path, target: Path, renames: Dict[str, str]) -> None:
    """The newer working copy stays the working copy; the other is filed under backups."""
    if not candidate.is_file():
        return
    existing = target / "working" / WORKING_NAME
    if not existing.is_file():
        _move(candidate, existing, renames)
        return
    older = candidate if candidate.stat().st_mtime <= existing.stat().st_mtime else existing
    _move(older, target / "backups" / f"{WORKING_NAME}.{_stamp()}.consolidated.bak", renames)
    if older is existing:
        _move(candidate, existing, renames)


def _retarget_metadata(metadata: Path, old: Path, target: Path, renames: Dict[str, str]) -> None:
    """Point every path field of a moved metadata file at the new directory."""
    data = json.loads(metadata.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return
    old_prefix, new_prefix = str(old), str(target)
    for key, value in data.items():
        if isinstance(value, str) and value in renames:
            data[key] = renames[value]
        elif isinstance(value, str) and value.startswith(old_prefix):
            data[key] = new_prefix + value[len(old_prefix):]
    metadata.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def _move(source: Path, destination: Path, renames: Dict[str, str]) -> Path:
    destination = _free_name(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    renames[str(source)] = str(destination)
    return destination


def _free_name(path: Path) -> Path:
    """``name.ext``, else ``name-1.ext``, ``name-2.ext``: the first that does not exist."""
    counter = 1
    candidate = path
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        counter += 1
    return candidate


def _files(directory: Path) -> List[Path]:
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.iterdir() if path.is_file())


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
