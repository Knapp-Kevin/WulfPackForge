import hashlib
import json
import logging
import os
import platform
import re
import shutil
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from subscripts.saveSafety import verify_fch_round_trip


logger = logging.getLogger(__name__)

SNAPSHOT_RETENTION = 10
BACKUP_RETENTION = 10


class WorkspaceError(Exception):
    """Base error for managed Wulfpack Forge workspace operations."""


class SourceChangedError(WorkspaceError):
    """Raised when the active source changed after Wulfpack Forge opened it."""


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return value or "character"


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_workspace_root(home: Optional[Path] = None, system_name: Optional[str] = None) -> Path:
    home = Path(home or Path.home())
    system_name = system_name or platform.system()

    if system_name == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    elif system_name == "Darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share")

    return base / "WulfpackForge"


@dataclass
class WorkspaceSession:
    character_id: str
    character_name: str
    source_path: str
    workspace_dir: str
    source_snapshot_path: str
    working_path: str
    backups_dir: str
    metadata_path: str
    opened_at: str
    opened_sha256: str
    expected_source_sha256: str
    expected_source_size: int
    expected_source_mtime_ns: int
    working_sha256: str
    player_id: Optional[int] = None
    last_applied_at: Optional[str] = None
    last_backup_path: Optional[str] = None

    def persist(self) -> None:
        path = Path(self.metadata_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        payload["state"] = "active"
        payload["schema_version"] = 1

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".metadata-",
            suffix=".json",
            dir=path.parent,
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True)
            temp_path = handle.name
        os.replace(temp_path, path)

    def source_matches_expected(self) -> bool:
        source = Path(self.source_path)
        if not source.is_file():
            return False
        return file_sha256(source) == self.expected_source_sha256

    def assert_source_unchanged(self) -> None:
        if not self.source_matches_expected():
            raise SourceChangedError(
                "The active character file changed after it was opened in Wulfpack Forge. "
                "Reload the character before applying changes so a newer Steam, Valheim, or external edit is not overwritten."
            )

    def update_after_apply(self, backup_path: Optional[str]) -> None:
        source = Path(self.source_path)
        stat = source.stat()
        self.expected_source_sha256 = file_sha256(source)
        self.expected_source_size = stat.st_size
        self.expected_source_mtime_ns = stat.st_mtime_ns
        self.working_sha256 = file_sha256(self.working_path)
        self.last_applied_at = _utc_iso()
        self.last_backup_path = backup_path
        self.persist()
        prune_workspace(Path(self.workspace_dir))


def create_workspace_session(
    source_path: str,
    root_save: dict,
    workspace_root: Optional[Path] = None,
) -> WorkspaceSession:
    source = Path(source_path).resolve()
    if not source.is_file():
        raise WorkspaceError(f"Character source does not exist: {source}")

    # Opening a workspace starts only after strict verification succeeds.
    verify_fch_round_trip(str(source))

    character_name = str(root_save.get("character_name") or source.stem).strip() or source.stem
    player_id = root_save.get("player_id")
    character_id = _character_id(character_name, player_id, root_save.get("date_created_unix"))
    workspace_dir, source_dir, working_dir, backups_dir = _workspace_dirs(workspace_root, character_id)
    opened_hash, stat = file_sha256(source), source.stat()
    snapshot_path = _snapshot_source(source, source_dir)
    working_path = _verified_working_copy(source, working_dir)
    session = WorkspaceSession(
        character_id=character_id, character_name=character_name, source_path=str(source),
        workspace_dir=str(workspace_dir), source_snapshot_path=str(snapshot_path),
        working_path=str(working_path), backups_dir=str(backups_dir),
        metadata_path=str(workspace_dir / "metadata.json"), opened_at=_utc_iso(),
        opened_sha256=opened_hash, expected_source_sha256=opened_hash,
        expected_source_size=stat.st_size, expected_source_mtime_ns=stat.st_mtime_ns,
        working_sha256=file_sha256(working_path),
        player_id=player_id if isinstance(player_id, int) else None,
    )
    session.persist()
    prune_workspace(Path(workspace_dir))
    return session


def prune_workspace(workspace_dir: Path, keep_snapshots: int = SNAPSHOT_RETENTION, keep_backups: int = BACKUP_RETENTION):
    """Delete the oldest opened snapshots and backups beyond the retention counts; the newest always stay."""
    removed = []
    for folder, keep in ((workspace_dir / "source", keep_snapshots), (workspace_dir / "backups", keep_backups)):
        if not folder.is_dir():
            continue
        files = sorted((p for p in folder.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
        for stale in files[keep:]:
            try:
                stale.unlink()
                removed.append(stale)
                logger.info("Pruned %s (retention %d)", stale, keep)
            except OSError as exc:
                logger.warning("Could not prune %s: %s", stale, exc)
    return removed


def _workspace_dirs(workspace_root: Optional[Path], character_id: str):
    root = Path(workspace_root or default_workspace_root())
    workspace_dir = root / "characters" / "active" / character_id
    dirs = (workspace_dir / "source", workspace_dir / "working", workspace_dir / "backups")
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)
    return (workspace_dir, *dirs)


def _character_id(character_name: str, player_id, date_created) -> str:
    """Stable per character: every copy of a save (active, .old, backups) shares one workspace."""
    identity_seed = f"{player_id if player_id is not None else ''}|{date_created if date_created is not None else ''}".encode("utf-8")
    identity = hashlib.sha256(identity_seed).hexdigest()[:12]
    return f"{_slug(character_name)}-{identity}"


def _snapshot_source(source: Path, source_dir: Path) -> Path:
    """Immutable copy of the source as it was opened; never overwrites an earlier snapshot."""
    snapshot_path = source_dir / f"{_utc_stamp()}-opened.fch"
    counter = 1
    while snapshot_path.exists():
        snapshot_path = source_dir / f"{_utc_stamp()}-opened-{counter}.fch"
        counter += 1
    shutil.copy2(source, snapshot_path)
    return snapshot_path


def _verified_working_copy(source: Path, working_dir: Path) -> Path:
    working_path = working_dir / "character.fch"
    temp_working = working_dir / ".character.fch.tmp"
    shutil.copy2(source, temp_working)
    verify_fch_round_trip(str(temp_working))
    os.replace(temp_working, working_path)
    return working_path


def store_verified_working_copy(
    candidate_path: str,
    session: WorkspaceSession,
    expected_root: Optional[dict] = None,
) -> str:
    verify_fch_round_trip(candidate_path, expected_root)

    destination = Path(session.working_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(".character.fch.tmp")
    shutil.copy2(candidate_path, temp_path)
    verify_fch_round_trip(str(temp_path), expected_root)
    os.replace(temp_path, destination)

    session.working_sha256 = file_sha256(destination)
    session.persist()
    return str(destination)
