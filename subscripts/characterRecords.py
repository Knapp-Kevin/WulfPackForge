"""One character, many states.

A *record* is a Valheim character identified by ``(player_id, date_created_unix)``
read from the verified container. A *state* is any file that verifies as that
identity: the active save, Valheim's ``.fch.old`` and ``_backup`` copies, and the
Wulfpack Forge workspace snapshots, working copy, and backups. Nothing here
writes to a save; restoring a state is a pending edit applied through Save Changes.
"""
import json
import os
import platform
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from subscripts.characterDiscovery import candidate_character_directories
from subscripts.saveErrors import SaveFormatError
from subscripts.saveSafety import verify_fch_round_trip
from subscripts.workspace import default_workspace_root

KIND_LABELS = {
    "active": "Active save", "game-old": "Valheim previous (.old)", "game-backup": "Valheim backup",
    "workspace-snapshot": "Opened snapshot", "workspace-working": "Working copy",
    "workspace-backup": "Pre-replace backup", "manual": "File",
}
INDEX_RELATIVE = Path("index") / "states.json"


@dataclass(frozen=True)
class CharacterState:
    path: str
    kind: str
    source: str
    name: str
    player_id: Optional[int]
    date_created: Optional[int]
    modified_at: float
    size: int
    version: Optional[int]
    valid: bool
    error: Optional[str] = None

    @property
    def kind_label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)

    @property
    def modified_label(self) -> str:
        return datetime.fromtimestamp(self.modified_at).strftime("%Y-%m-%d %H:%M")


@dataclass
class CharacterRecord:
    key: str
    name: str
    states: List[CharacterState] = field(default_factory=list)

    @property
    def head(self) -> Optional[CharacterState]:
        active = [s for s in self.states if s.kind == "active" and s.valid]
        if active:
            return active[0]
        valid = [s for s in self.states if s.valid]
        if valid:
            return valid[0]
        return self.states[0] if self.states else None

    @property
    def valid(self) -> bool:
        return any(s.valid for s in self.states)

    @property
    def display_label(self) -> str:
        head = self.head
        count = f"{len(self.states)} state{'s' if len(self.states) != 1 else ''}"
        status = "" if self.valid else " [needs attention]"
        where = f" — {head.source} — {head.modified_label}" if head else ""
        return f"{self.name} — {count}{where}{status}"


def character_key(player_id: Optional[int], date_created: Optional[int]) -> str:
    return f"{player_id}:{date_created}"


def classify_path(path: Path, workspace_root: Path) -> str:
    """Kind of a save file from where it lives and how it is named."""
    try:
        path.resolve().relative_to(workspace_root.resolve())
        parent = path.parent.name
        return {"source": "workspace-snapshot", "working": "workspace-working", "backups": "workspace-backup"}.get(parent, "manual")
    except ValueError:
        pass
    lowered = path.name.lower()
    if lowered.endswith(".fch.old"):
        return "game-old"
    if "_backup" in lowered:
        return "game-backup"
    return "active" if lowered.endswith(".fch") else "manual"


class StateCache:
    """Remembers parsed identity per path keyed on size and mtime so unchanged files skip verification."""

    def __init__(self, path: Optional[Path]):
        self.path = path
        self.entries: Dict[str, dict] = {}
        if path and path.is_file():
            try:
                self.entries = json.loads(path.read_text(encoding="utf-8")).get("entries", {})
            except (OSError, ValueError):
                self.entries = {}

    def lookup(self, path: str, size: int, mtime_ns: int) -> Optional[dict]:
        entry = self.entries.get(path)
        if entry and entry.get("size") == size and entry.get("mtime_ns") == mtime_ns:
            return entry["fields"]
        return None

    def store(self, path: str, size: int, mtime_ns: int, fields: dict) -> None:
        self.entries[path] = {"size": size, "mtime_ns": mtime_ns, "fields": fields}

    def save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"schema_version": 1, "entries": self.entries}), encoding="utf-8")
        except OSError:
            pass


def _identity_fields(path: Path) -> dict:
    try:
        parsed = verify_fch_round_trip(str(path))
        name = (parsed.get("character_name") or path.stem).strip() or path.stem
        return {"name": name, "player_id": parsed.get("player_id"), "date_created": parsed.get("date_created_unix"),
                "version": parsed.get("version"), "valid": True, "error": None}
    except (SaveFormatError, OSError, ValueError, KeyError) as exc:
        stem = path.name.split(".")[0]
        return {"name": stem, "player_id": None, "date_created": None, "version": None, "valid": False, "error": str(exc)}


def state_from_file(path: Path, source: str, kind: str, cache: StateCache) -> CharacterState:
    stat = path.stat()
    key = os.path.normcase(str(path))
    fields = cache.lookup(key, stat.st_size, stat.st_mtime_ns)
    if fields is None:
        fields = _identity_fields(path)
        cache.store(key, stat.st_size, stat.st_mtime_ns, fields)
    return CharacterState(path=str(path), kind=kind, source=source, modified_at=stat.st_mtime, size=stat.st_size, **fields)


def _game_files(directory: Path) -> List[Path]:
    try:
        return [p for pattern in ("*.fch", "*.fch.old") for p in directory.glob(pattern) if p.is_file()]
    except OSError:
        return []


def _workspace_files(workspace_root: Path) -> List[Path]:
    active = workspace_root / "characters" / "active"
    if not active.is_dir():
        return []
    found = []
    for pattern in ("*/source/*.fch", "*/working/*.fch", "*/backups/*"):
        found.extend(p for p in active.glob(pattern) if p.is_file())
    return found


def scan_states(home: Optional[Path] = None, system_name: Optional[str] = None,
                workspace_root: Optional[Path] = None, cache: Optional[StateCache] = None) -> List[CharacterState]:
    """Every save-like file in the game folders and the workspace, verified (or cached) and typed."""
    workspace_root = Path(workspace_root or default_workspace_root(home, system_name or platform.system()))
    cache = cache if cache is not None else StateCache(workspace_root / INDEX_RELATIVE)
    states: List[CharacterState] = []
    seen = set()
    for directory, source in candidate_character_directories(home, system_name):
        for path in _game_files(directory):
            _append_state(states, seen, path, source, classify_path(path, workspace_root), cache)
    for path in _workspace_files(workspace_root):
        _append_state(states, seen, path, "Wulfpack Forge workspace", classify_path(path, workspace_root), cache)
    cache.save()
    return states


def _append_state(states, seen, path: Path, source: str, kind: str, cache: StateCache) -> None:
    try:
        resolved = path.resolve()
    except OSError:
        return
    key = os.path.normcase(str(resolved))
    if key in seen:
        return
    seen.add(key)
    states.append(state_from_file(resolved, source, kind, cache))


def build_records(states: Iterable[CharacterState]) -> List[CharacterRecord]:
    """Group states by identity; unverifiable files stand alone. Newest first inside and across records."""
    grouped: Dict[str, CharacterRecord] = {}
    for state in sorted(states, key=lambda s: -s.modified_at):
        key = character_key(state.player_id, state.date_created) if state.valid else f"invalid:{os.path.normcase(state.path)}"
        record = grouped.setdefault(key, CharacterRecord(key=key, name=state.name))
        record.states.append(state)
    records = list(grouped.values())
    for record in records:
        head = record.head
        if head:
            record.name = head.name
    records.sort(key=lambda r: (not r.valid, -(r.head.modified_at if r.head else 0), r.name.lower()))
    return records


def discover_character_records(home: Optional[Path] = None, system_name: Optional[str] = None,
                               workspace_root: Optional[Path] = None) -> List[CharacterRecord]:
    return build_records(scan_states(home, system_name, workspace_root))


def _canonical(path: str) -> str:
    """Case-folded real path; resolves Windows 8.3 short names so the same file always compares equal."""
    return os.path.normcase(os.path.realpath(path))


def find_state(records: Iterable[CharacterRecord], path: str) -> Optional[Tuple[CharacterRecord, CharacterState]]:
    wanted = _canonical(path)
    for record in records:
        for state in record.states:
            if _canonical(state.path) == wanted:
                return record, state
    return None
