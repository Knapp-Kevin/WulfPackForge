import sys
from pathlib import Path

from PySide6.QtGui import QIcon, QImageReader


APP_NAME = "Wulfpack Forge"
APP_SUBTITLE = "Character Editor for Valheim"
APP_AUTHOR = "Frostwulf"
APP_VERSION = "0.9.0-rc.1"
APP_WINDOW_TITLE = f"{APP_NAME} | {APP_SUBTITLE} | v{APP_VERSION}"
BANNER_RELATIVE_PATH = "assets/wulfpack-forge-banner.jpg"
MIN_BANNER_BYTES = 12_000
APP_ICON_RELATIVE_PATH = "assets/FrostWulf-favicon.png"
APP_ICO_RELATIVE_PATH = "assets/wulfpack-forge.ico"


def resource_path(relative_path: str) -> Path:
    """Resolve a repository resource in source runs and PyInstaller bundles."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / relative_path
    return Path(__file__).resolve().parents[1] / relative_path


def banner_path() -> Path:
    return resource_path(BANNER_RELATIVE_PATH)


def app_icon_path() -> Path:
    return resource_path(APP_ICON_RELATIVE_PATH)


def app_icon() -> QIcon:
    """The Frostwulf mark as a QIcon, or a null icon when the asset is absent."""
    path = app_icon_path()
    return QIcon(str(path)) if path.is_file() else QIcon()


def banner_is_usable() -> bool:
    """Verify the approved banner asset is present in source and packaged runs.

    Visual quality is reviewed separately through the README/UI itself. This guard
    exists to prevent accidental omission from source checkout or PyInstaller
    bundles, not to turn CI into an image-quality judge.
    """
    path = banner_path()
    if not path.is_file() or path.stat().st_size < MIN_BANNER_BYTES:
        return False

    reader = QImageReader(str(path))
    return reader.canRead() and not reader.read().isNull()
