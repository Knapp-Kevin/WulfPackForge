"""Opt-in extraction of item icons from the player's own Valheim installation.

The game keeps item icons as sprites inside its streaming asset bundles. When the user asks for it,
this module follows the game's own reference (item prefab -> ItemDrop -> icons) and writes one PNG per
icon into the managed workspace. The game files are only read; the PNGs never leave the user's machine
through Wulfpack Forge. UnityPy is an optional dependency: without it the feature reports itself as
unavailable and the bundled fallback art stays in use.
"""
import importlib.util
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

BUNDLES_RELATIVE = Path("valheim_Data") / "StreamingAssets" / "SoftRef" / "Bundles"
STEAM_GAME_RELATIVE = Path("steamapps") / "common" / "Valheim"
INDEX_NAME = "index.json"
INSTALL_HINT = "Icon extraction needs the optional UnityPy package: pip install -r requirements-optional.txt"
Progress = Optional[Callable[[str, int, int], None]]


@dataclass
class ExtractionReport:
    game_dir: str
    cache_dir: str
    requested: int = 0
    extracted: int = 0
    missing: List[str] = field(default_factory=list)
    seconds: float = 0.0


def extraction_available() -> bool:
    return importlib.util.find_spec("UnityPy") is not None


def is_game_directory(path: Optional[Path]) -> bool:
    return bool(path) and (Path(path) / BUNDLES_RELATIVE).is_dir()


def find_game_directory(steam_root: Optional[Path]) -> Optional[Path]:
    """The Valheim directory under a Steam install, or None when it is not there."""
    if steam_root is None:
        return None
    candidate = Path(steam_root) / STEAM_GAME_RELATIVE
    return candidate if is_game_directory(candidate) else None


def icon_cache_dir(workspace_root: Path) -> Path:
    return Path(workspace_root) / "icons"


def load_index(cache_dir: Path) -> dict:
    index_path = Path(cache_dir) / INDEX_NAME
    if not index_path.is_file():
        return {}
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Icon index unreadable: %s", index_path)
        return {}


def cached_icon_path(cache_dir: Path, prefab: str, variant: int = 0) -> Optional[Path]:
    """The extracted PNG for a prefab and variant, or None; variant 0 falls back to the base icon."""
    suffix = f"_{variant}" if variant else ""
    path = Path(cache_dir) / f"{prefab}{suffix}.png"
    if path.is_file():
        return path
    base = Path(cache_dir) / f"{prefab}.png"
    return base if variant and base.is_file() else None


def _item_drop_icons(components, deref) -> Optional[list]:
    """Icon references from the first ItemDrop component, or None when the prefab is not an item."""
    for component in components:
        try:
            behaviour = deref(component.component if hasattr(component, "component") else component)
            if behaviour is None or behaviour.type.name != "MonoBehaviour":
                continue
            tree = behaviour.read_typetree()
        except Exception:  # unreadable component: not the one we want
            continue
        if "m_itemData" in tree:
            return list(tree["m_itemData"]["m_shared"].get("m_icons") or [])
    return None


def collect_item_icons(objects: Iterable, wanted: set, deref, resolve_icon) -> Dict[str, list]:
    """Map each wanted prefab name to its icon sprites, following prefab -> ItemDrop -> m_icons."""
    found: Dict[str, list] = {}
    for obj in objects:
        if obj.type.name != "GameObject":
            continue
        try:
            game_object = obj.read()
        except Exception:
            continue
        name = game_object.m_Name
        if name not in wanted or name in found:
            continue
        refs = _item_drop_icons(game_object.m_Components, deref)
        if refs is None:
            continue
        sprites = [sprite for sprite in (resolve_icon(ref, obj) for ref in refs) if sprite is not None]
        if sprites:
            found[name] = sprites
    return found


def _unitypy_deref(pointer):
    try:
        return pointer.deref()
    except Exception:
        return None


def _unitypy_icon(ref: dict, owner):
    from UnityPy.classes import PPtr  # optional dependency, imported only when extracting

    try:
        pointer = PPtr(m_FileID=ref["m_FileID"], m_PathID=ref["m_PathID"])
        pointer.assetsfile = owner.assets_file
        return pointer.deref().read()
    except Exception:
        return None


def save_sprites(found: Dict[str, list], cache_dir: Path, progress: Progress = None) -> Dict[str, List[str]]:
    """Write prefab.png for the first icon and prefab_<n>.png for variants; returns the index mapping."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, List[str]] = {}
    for done, (prefab, sprites) in enumerate(found.items(), start=1):
        files = []
        for index, sprite in enumerate(sprites):
            target = cache_dir / (f"{prefab}.png" if index == 0 else f"{prefab}_{index}.png")
            try:
                sprite.image.save(target)
                files.append(target.name)
            except Exception:
                logger.exception("Could not save icon %s", target)
        if files:
            written[prefab] = files
        if progress:
            progress("Saving icons", done, len(found))
    return written


def extract_icons(game_dir: Path, prefabs: Iterable[str], cache_dir: Path, progress: Progress = None) -> ExtractionReport:
    """Read the game's bundles once, resolve every requested prefab's icons, and write them to the cache."""
    import UnityPy  # optional dependency

    started = time.monotonic()
    wanted = set(prefabs)
    report = ExtractionReport(game_dir=str(game_dir), cache_dir=str(cache_dir), requested=len(wanted))
    if progress:
        progress("Reading game bundles (this takes a minute or two)", 0, 1)
    environment = UnityPy.load(str(Path(game_dir) / BUNDLES_RELATIVE))
    if progress:
        progress("Resolving item icons", 0, 1)
    found = collect_item_icons(environment.objects, wanted, _unitypy_deref, _unitypy_icon)
    written = save_sprites(found, cache_dir, progress)
    index = {"game_dir": str(game_dir), "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"), "icons": written}
    (Path(cache_dir) / INDEX_NAME).write_text(json.dumps(index, indent=1, sort_keys=True), encoding="utf-8")
    report.extracted = len(written)
    report.missing = sorted(wanted - set(written))
    report.seconds = time.monotonic() - started
    logger.info("Extracted %d of %d icons from %s in %.0fs", report.extracted, report.requested, game_dir, report.seconds)
    return report
