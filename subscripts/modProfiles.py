"""Where BepInEx plugin sets live: the game folder itself and the mod managers' profile folders."""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

PLUGINS = Path("BepInEx") / "plugins"
MANAGER_PROFILE_ROOTS = (
    ("Thunderstore", Path("Thunderstore Mod Manager") / "DataFolder" / "Valheim" / "profiles"),
    ("r2modman", Path("r2modmanPlus-local") / "Valheim" / "profiles"),
)


@dataclass(frozen=True)
class ModProfile:
    name: str
    bepinex_dir: Path

    @property
    def plugins_dir(self) -> Path:
        return self.bepinex_dir / "plugins"

    @property
    def config_dir(self) -> Path:
        return self.bepinex_dir / "config"

    def plugin_count(self) -> int:
        if not self.plugins_dir.is_dir():
            return 0
        return sum(1 for _root, _dirs, files in os.walk(self.plugins_dir) for f in files if f.lower().endswith(".dll"))


def profile_from_directory(path: Path, name: Optional[str] = None) -> Optional[ModProfile]:
    """Accept a BepInEx folder or its parent; None when there is no plugins folder beneath."""
    path = Path(path)
    for candidate in (path, path / "BepInEx"):
        if (candidate / "plugins").is_dir():
            return ModProfile(name or path.name, candidate)
    return None


def discover_profiles(game_dir: Optional[Path] = None, appdata: Optional[Path] = None) -> List[ModProfile]:
    """Game-folder BepInEx first, then every manager profile that has a plugins folder."""
    profiles: List[ModProfile] = []
    if game_dir is not None:
        found = profile_from_directory(Path(game_dir), "Game folder (BepInEx)")
        if found:
            profiles.append(found)
    appdata = Path(appdata) if appdata else Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    for manager, relative in MANAGER_PROFILE_ROOTS:
        root = appdata / relative
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            found = profile_from_directory(entry, f"{manager}: {entry.name}")
            if found:
                profiles.append(found)
    return profiles
