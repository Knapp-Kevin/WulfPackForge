import os
import platform
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from subscripts.playerDataUtil import unpack_player_data_hex
from subscripts.saveErrors import SaveFormatError
from subscripts.saveSafety import verify_fch_round_trip


VALHEIM_APP_ID = "892970"


@dataclass(frozen=True)
class CharacterSave:
    path: str
    name: str
    source: str
    modified_at: float
    version: Optional[int]
    valid: bool
    error: Optional[str] = None
    player_id: Optional[int] = None
    date_created: Optional[int] = None

    @property
    def modified_label(self) -> str:
        return datetime.fromtimestamp(self.modified_at).strftime("%Y-%m-%d %H:%M")

    @property
    def display_label(self) -> str:
        status = "" if self.valid else " [needs attention]"
        return f"{self.name} — {self.source} — {self.modified_label}{status}"


def _existing_directories(paths: Iterable[Path]) -> List[Path]:
    found = []
    seen = set()
    for path in paths:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        key = os.path.normcase(str(resolved))
        if key not in seen and resolved.is_dir():
            seen.add(key)
            found.append(resolved)
    return found


def _local_save_roots(home: Path, system_name: str) -> List[Path]:
    if system_name == "Windows":
        base = home / "AppData" / "LocalLow" / "IronGate" / "Valheim"
        return [base / "characters_local", base / "characters"]

    if system_name == "Darwin":
        bases = [
            home / "Library" / "Application Support" / "com.coffeestain.Valheim",
            home / "Library" / "Application Support" / "unity.IronGate.Valheim-macOS-Custom",
            home / "Containers" / "Valheim" / "Data" / "Library" / "Application Support" / "com.coffeestain.Valheim",
        ]
        return [child for base in bases for child in (base / "characters_local", base / "characters")]

    base = home / ".config" / "unity3d" / "IronGate" / "Valheim"
    return [base / "characters_local", base / "characters"]


def registry_steam_path() -> Optional[Path]:
    """Steam's install directory from the current user's registry (Windows only); None when unavailable."""
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, kind = winreg.QueryValueEx(key, "SteamPath")
    except OSError:
        return None
    if kind != winreg.REG_SZ or not value:
        return None
    return Path(value)


def steam_roots(home: Optional[Path] = None, system_name: Optional[str] = None) -> List[Path]:
    """Where a Steam install may be on this platform, most likely first; existence is not checked."""
    home = Path(home or Path.home())
    system_name = system_name or platform.system()
    roots: List[Path] = []
    if system_name == "Windows":
        registry_root = registry_steam_path()
        if registry_root is not None:
            roots.append(registry_root)
        for env_name in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
            base = os.environ.get(env_name)
            if base:
                roots.append(Path(base) / "Steam")
        steam_dir = os.environ.get("STEAM_DIR")
        if steam_dir:
            roots.append(Path(steam_dir))
    elif system_name == "Darwin":
        roots.append(home / "Library" / "Application Support" / "Steam")
    else:
        roots.extend([home / ".steam" / "steam", home / ".local" / "share" / "Steam"])
    return roots


def _steam_userdata_roots(home: Path, system_name: str) -> List[Path]:
    return [root / "userdata" for root in steam_roots(home, system_name)]


def candidate_character_directories(
    home: Optional[Path] = None,
    system_name: Optional[str] = None,
) -> List[tuple[Path, str]]:
    """Return character directories that already exist on the local computer.

    Steam Cloud entries here are local synchronized copies under Steam's userdata
    tree. Wulfpack Forge does not query or download remote Steam Cloud storage.
    """
    home = Path(home or Path.home())
    system_name = system_name or platform.system()

    candidates: List[tuple[Path, str]] = [
        (path, "Local") for path in _local_save_roots(home, system_name)
    ]
    for userdata_root in _existing_directories(_steam_userdata_roots(home, system_name)):
        candidates.extend(_steam_character_dirs(userdata_root))
    return _unique_existing_dirs(candidates)


def _steam_character_dirs(userdata_root: Path) -> List[tuple[Path, str]]:
    try:
        account_dirs = [path for path in userdata_root.iterdir() if path.is_dir()]
    except OSError:
        return []
    found = []
    for account_dir in account_dirs:
        remote = account_dir / VALHEIM_APP_ID / "remote"
        found.append((remote / "characters", "Steam Cloud (local copy)"))
        found.append((remote / "characters_local", "Steam local copy"))
    return found


def _unique_existing_dirs(candidates: List[tuple[Path, str]]) -> List[tuple[Path, str]]:
    found = []
    seen = set()
    for path, source in candidates:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        key = os.path.normcase(str(resolved))
        if key in seen or not resolved.is_dir():
            continue
        seen.add(key)
        found.append((resolved, source))
    return found


def inspect_character_save(path: Path, source: str) -> CharacterSave:
    modified_at = path.stat().st_mtime
    fallback_name = path.stem

    try:
        parsed = verify_fch_round_trip(str(path))
        unpack_player_data_hex(parsed.get("player_data_hex") or "")
        return CharacterSave(
            path=str(path),
            name=(parsed.get("character_name") or fallback_name).strip() or fallback_name,
            source=source,
            modified_at=modified_at,
            version=parsed.get("version"),
            valid=True,
            player_id=parsed.get("player_id"),
            date_created=parsed.get("date_created_unix"),
        )
    except (SaveFormatError, OSError, ValueError, KeyError) as exc:
        return CharacterSave(
            path=str(path),
            name=fallback_name,
            source=source,
            modified_at=modified_at,
            version=None,
            valid=False,
            error=str(exc),
        )


def discover_character_saves(
    home: Optional[Path] = None,
    system_name: Optional[str] = None,
) -> List[CharacterSave]:
    results = []
    seen_files = set()
    for directory, source in candidate_character_directories(home, system_name):
        for resolved in _character_files(directory):
            key = os.path.normcase(str(resolved))
            if key in seen_files:
                continue
            seen_files.add(key)
            results.append(inspect_character_save(resolved, source))
    results.sort(key=lambda item: (not item.valid, -item.modified_at, item.name.lower()))
    return results


def _character_files(directory: Path) -> List[Path]:
    """Resolved ``.fch`` files in a directory; unreadable directories or entries are skipped."""
    found = []
    try:
        for path in directory.glob("*.fch"):
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved.is_file():
                found.append(resolved)
    except OSError:
        return found
    return found
