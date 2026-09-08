"""Apply a scanned mod catalog to the running editor: skill names, item definitions, icon paths."""
import logging
from pathlib import Path
from typing import Dict, Optional

from data.items import ItemDefinition, register_items
from data.skills import VALHEIM_SKILLS
from subscripts.modScan import catalog_paths, load_catalog

logger = logging.getLogger(__name__)

_SKILLS: Dict[int, str] = {}
_ICONS_DIR: Optional[Path] = None
_PROFILE: Optional[str] = None


def mods_dir(workspace_root: Path) -> Path:
    return Path(workspace_root) / "mods"


def apply_overrides(workspace_root: Path) -> int:
    """Load the catalog under the workspace (if any) and register it; returns the number of items registered."""
    global _SKILLS, _ICONS_DIR, _PROFILE
    directory = mods_dir(workspace_root)
    catalog = load_catalog(directory)
    if not catalog:
        return 0
    _PROFILE = catalog.get("profile")
    _ICONS_DIR = catalog_paths(directory)[1]
    _SKILLS = {int(k): v for k, v in (catalog.get("skills") or {}).items() if str(k).lstrip("-").isdigit()}
    definitions = [_definition(prefab, record) for prefab, record in (catalog.get("items") or {}).items()]
    registered = register_items(definitions)
    logger.info("Mod overrides from %s: %d skills, %d items registered", _PROFILE, len(_SKILLS), registered)
    return registered


def _definition(prefab: str, record: dict) -> ItemDefinition:
    return ItemDefinition(prefab=prefab, display_name=record.get("display_name") or prefab,
                          max_stack=record.get("max_stack"), max_quality=record.get("max_quality"),
                          variants=record.get("variants"), item_type=record.get("item_type"))


def reset_overrides() -> None:
    """Forget a loaded catalog (tests, or before re-applying)."""
    global _SKILLS, _ICONS_DIR, _PROFILE
    _SKILLS, _ICONS_DIR, _PROFILE = {}, None, None


def active_profile() -> Optional[str]:
    return _PROFILE


def skill_name(skill_id: int) -> Optional[str]:
    """Vanilla name first, then the scanned identifier; None when neither knows the id."""
    return VALHEIM_SKILLS.get(skill_id) or _SKILLS.get(abs(int(skill_id)))


def skill_label(skill_id: int) -> str:
    return skill_name(skill_id) or f"Unknown ({skill_id})"


def mod_icons_dir() -> Optional[Path]:
    return _ICONS_DIR
