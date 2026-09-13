import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from data.items import CATALOG_GAME_VERSION


SAVE_STATE_VERIFIED = "Verified"
SAVE_STATE_NEEDS_ATTENTION = "Needs attention"
SAVE_STATE_COMPATIBILITY_UNVERIFIED = "Compatibility unverified"

# Character-save container versions this codec round-trips byte-identical. Versions 40-43
# are evidenced by real saves (22 v40-v42 files and 18 v43 files, 2026-09-06); version 46
# is evidenced by a synthetic fixture only, because no real v46 save is committed to this
# repository. The player payload is gated separately by SUPPORTED_PLAYER_DATA_VERSIONS;
# any other outer version is read-only.
SUPPORTED_CHARACTER_SAVE_VERSIONS = frozenset({40, 41, 42, 43, 46})


@dataclass(frozen=True)
class SaveHealthReport:
    state: str
    verification_ok: bool
    writable: bool
    save_version: Optional[int]
    source: str
    modified_at: Optional[float]
    catalog_game_version: Optional[str]
    detail: str
    error: Optional[str] = None
    backup_path: Optional[str] = None
    source_changed: bool = False

    @property
    def save_version_label(self) -> str:
        return f"v{self.save_version}" if self.save_version is not None else "unknown"

    @property
    def modified_label(self) -> str:
        if self.modified_at is None:
            return "unknown"
        try:
            return datetime.fromtimestamp(self.modified_at).strftime("%Y-%m-%d %H:%M")
        except (OSError, OverflowError, ValueError):
            return "unknown"

    @property
    def catalog_label(self) -> str:
        if self.catalog_game_version:
            return f"Valheim {self.catalog_game_version}"
        return "curated fallback"

    @property
    def backup_label(self) -> Optional[str]:
        return os.path.basename(self.backup_path) if self.backup_path else None


def build_save_health_report(
    *,
    valid: bool,
    version: Optional[int],
    source: str,
    modified_at: Optional[float],
    error: Optional[str] = None,
    backup_path: Optional[str] = None,
    catalog_game_version: Optional[str] = CATALOG_GAME_VERSION,
    source_changed: bool = False,
    payload_supported: bool = True,
) -> SaveHealthReport:
    source = (source or "File").strip() or "File"
    common = dict(save_version=version, source=source, modified_at=modified_at,
                  catalog_game_version=catalog_game_version, backup_path=backup_path)

    if not valid:
        detail = "This file failed strict verification and is not available for editing."
        if error:
            detail += f" {error}"
        return SaveHealthReport(state=SAVE_STATE_NEEDS_ATTENTION, verification_ok=False, writable=False,
                                detail=detail, error=error, source_changed=source_changed, **common)
    if source_changed:
        return SaveHealthReport(
            state=SAVE_STATE_NEEDS_ATTENTION, verification_ok=True, writable=False,
            detail=("The active character file changed outside Wulfpack Forge after it was opened. "
                    "Reload the character before applying changes so a newer Steam, Valheim, or external edit is not overwritten."),
            error="External source change detected", source_changed=True, **common)
    if version not in SUPPORTED_CHARACTER_SAVE_VERSIONS or not payload_supported:
        return SaveHealthReport(
            state=SAVE_STATE_COMPATIBILITY_UNVERIFIED, verification_ok=True, writable=False,
            detail=(f"Checksum and structure verified, but {_compatibility_reason(version)} "
                    "the current write-validated set. You can inspect the character, but Save Changes "
                    "is disabled until compatibility is validated."),
            error=None, source_changed=False, **common)
    return SaveHealthReport(
        state=SAVE_STATE_VERIFIED, verification_ok=True, writable=True,
        detail=(f"Checksum and structure verified. Save version {version} is in the current "
                "write-validated set. Wulfpack Forge keeps a protected workspace snapshot before edits are applied."),
        error=None, source_changed=False, **common)


def _compatibility_reason(version: Optional[int]) -> str:
    if version in SUPPORTED_CHARACTER_SAVE_VERSIONS:
        return "the player data inside it uses a layout version outside"
    version_text = "unknown" if version is None else str(version)
    return f"save version {version_text} is outside"
