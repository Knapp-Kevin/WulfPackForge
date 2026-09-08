"""Read-only scan of a BepInEx plugin set: skill identifiers, localisation, and the override catalog.

Plugin DLLs are read as bytes; no plugin code runs. Skill identifiers are recovered from the string
literals in the DLLs and matched to save ids through Valheim's stable hash. Item names and icons come
from the asset bundles embedded in the DLLs (see modItems, which needs the optional UnityPy).
"""
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from subscripts.modProfiles import ModProfile
from subscripts.stableHash import skill_id_for

logger = logging.getLogger(__name__)

CATALOG_NAME = "catalog.json"
ICONS_DIR = "icons"
_UTF16_LITERAL = re.compile(rb"(?:[\x20-\x7e]\x00){3,64}")
_REJECT = re.compile(r"[\\/{}<>%\"]|^\s|\s$")
Progress = Optional[Callable[[str, int, int], None]]


@dataclass
class ScanReport:
    profile: str
    catalog_path: str
    dll_count: int = 0
    identifier_count: int = 0
    item_count: int = 0
    icon_count: int = 0
    items_available: bool = True
    seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


def plugin_dlls(plugins_dir: Path) -> List[Path]:
    return sorted(p for p in Path(plugins_dir).rglob("*.dll"))


def dll_strings(data: bytes) -> set:
    """Printable UTF-16 literals of 3 to 64 characters, as .NET stores string constants."""
    return {match.group().decode("utf-16-le") for match in _UTF16_LITERAL.finditer(data)}


def looks_like_identifier(text: str) -> bool:
    return not _REJECT.search(text)


def identifier_hashes(dlls: Iterable[Path], progress: Progress = None) -> Dict[int, str]:
    """Map each plausible identifier's skill id to the identifier; first DLL wins on a collision."""
    dlls = list(dlls)
    found: Dict[int, str] = {}
    for done, dll in enumerate(dlls, start=1):
        try:
            strings = dll_strings(dll.read_bytes())
        except OSError:
            logger.warning("Could not read plugin %s", dll)
            continue
        for text in strings:
            if looks_like_identifier(text):
                found.setdefault(skill_id_for(text), text)
        if progress:
            progress("Reading plugin strings", done, len(dlls))
    return found


def _english_json_files(root: Path) -> List[Path]:
    files = []
    for path in Path(root).rglob("*.json"):
        parts = [part.lower() for part in path.relative_to(root).parts]
        if any("english" in part for part in parts):
            files.append(path)
    return sorted(files)


def _flatten(value, out: Dict[str, str]) -> None:
    if isinstance(value, dict):
        for key, inner in value.items():
            if isinstance(inner, str):
                out.setdefault(str(key).lstrip("$"), inner)
            else:
                _flatten(inner, out)
    elif isinstance(value, list):
        for inner in value:
            _flatten(inner, out)


def load_localisation(profile: ModProfile) -> Dict[str, str]:
    """English token -> text from every mod's translation JSON under plugins and config."""
    texts: Dict[str, str] = {}
    for root in (profile.plugins_dir, profile.config_dir):
        if not root.is_dir():
            continue
        for path in _english_json_files(root):
            try:
                _flatten(json.loads(path.read_text(encoding="utf-8-sig")), texts)
            except (OSError, ValueError):
                logger.warning("Skipping unreadable translation %s", path)
    return texts


def display_name(token: Optional[str], texts: Dict[str, str], prefab: str) -> str:
    """Translate a ``$token``; a literal name passes through; otherwise humanise the token or prefab."""
    if token and not token.startswith("$"):
        return token
    key = (token or "").lstrip("$")
    if key in texts:
        return texts[key]
    source = key or prefab
    for prefix in ("item_", "vapok_mod_item_"):
        if source.startswith(prefix):
            source = source[len(prefix):]
    return source.replace("_", " ").strip().title() or prefab


def catalog_paths(mods_dir: Path):
    return Path(mods_dir) / CATALOG_NAME, Path(mods_dir) / ICONS_DIR


def write_catalog(mods_dir: Path, profile: ModProfile, skills: Dict[int, str], items: Dict[str, dict]) -> Path:
    catalog_path, _icons = catalog_paths(mods_dir)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    document = {"schema_version": 1, "profile": profile.name, "bepinex_dir": str(profile.bepinex_dir),
                "scanned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "skills": {str(skill_id): name for skill_id, name in sorted(skills.items())}, "items": items}
    catalog_path.write_text(json.dumps(document, indent=1, sort_keys=True), encoding="utf-8")
    return catalog_path


def load_catalog(mods_dir: Path) -> dict:
    catalog_path, _icons = catalog_paths(mods_dir)
    if not catalog_path.is_file():
        return {}
    try:
        return json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Mod catalog unreadable: %s", catalog_path)
        return {}


def scan_profile(profile: ModProfile, mods_dir: Path, progress: Progress = None) -> ScanReport:
    """Skills from DLL strings, items and icons from embedded bundles (when UnityPy is present)."""
    from subscripts.modItems import items_available, scan_items  # optional half

    started = time.monotonic()
    dlls = plugin_dlls(profile.plugins_dir)
    report = ScanReport(profile=profile.name, catalog_path="", dll_count=len(dlls))
    skills = identifier_hashes(dlls, progress)
    report.identifier_count = len(skills)
    items: Dict[str, dict] = {}
    report.items_available = items_available()
    if report.items_available:
        texts = load_localisation(profile)
        items, report.icon_count, report.errors = scan_items(dlls, texts, catalog_paths(mods_dir)[1], progress)
    report.item_count = len(items)
    report.catalog_path = str(write_catalog(mods_dir, profile, skills, items))
    report.seconds = time.monotonic() - started
    logger.info("Mod scan of %s: %d DLLs, %d identifiers, %d items, %d icons in %.0fs",
                profile.name, report.dll_count, report.identifier_count, report.item_count, report.icon_count, report.seconds)
    return report
