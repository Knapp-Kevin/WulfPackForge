"""Per-file verdict cache for character discovery.

A verdict ("this file verifies as character X" or "this build cannot read it") is remembered per
path so unchanged files skip the full parse on the next scan. It is trusted only when the file's
size and mtime still match and the cache was written by a build with the same supported-version
sets, so a newer build re-verifies what an older one refused (phase 45, issue #43 defect 3). A
path not seen during the scan is dropped when the cache is saved, so vanished files leave no
trace.
"""
import json
from pathlib import Path
from typing import Dict, Optional, Set

from subscripts.playerDataUtil import SUPPORTED_PLAYER_DATA_VERSIONS
from subscripts.saveHealth import SUPPORTED_CHARACTER_SAVE_VERSIONS

SCHEMA_VERSION = 2
CACHE_BUILD_KEY = (
    "container:" + ",".join(str(version) for version in sorted(SUPPORTED_CHARACTER_SAVE_VERSIONS))
    + " payload:" + ",".join(".".join(str(part) for part in triple) for triple in sorted(SUPPORTED_PLAYER_DATA_VERSIONS))
)


class StateCache:
    """Remembers parsed identity per path keyed on size, mtime and the build's supported versions."""

    def __init__(self, path: Optional[Path], build_key: str = CACHE_BUILD_KEY):
        self.path = path
        self.build_key = build_key
        self.entries: Dict[str, dict] = {}
        self._touched: Set[str] = set()
        if path and path.is_file():
            self.entries = _load(path, build_key)

    def lookup(self, path: str, size: int, mtime_ns: int) -> Optional[dict]:
        self._touched.add(path)
        entry = self.entries.get(path)
        if entry and entry.get("size") == size and entry.get("mtime_ns") == mtime_ns:
            return entry["fields"]
        return None

    def store(self, path: str, size: int, mtime_ns: int, fields: dict) -> None:
        self._touched.add(path)
        self.entries[path] = {"size": size, "mtime_ns": mtime_ns, "fields": fields}

    def save(self) -> None:
        """Write the entries looked up or stored during this scan; anything else is forgotten."""
        if not self.path:
            return
        kept = {key: value for key, value in self.entries.items() if key in self._touched}
        payload = {"schema_version": SCHEMA_VERSION, "build": self.build_key, "entries": kept}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass


def _load(path: Path, build_key: str) -> Dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("build") != build_key:
        return {}
    entries = data.get("entries")
    return entries if isinstance(entries, dict) else {}
