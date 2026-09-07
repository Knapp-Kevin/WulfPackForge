#!/usr/bin/env python3
"""Generate assets/wulfpack-forge.ico from the Frostwulf PNG using Qt only.

The PNG is the source of truth; the .ico is committed so CI and PyInstaller
need no extra imaging dependency. Re-run after replacing the PNG.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QImageWriter

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "assets" / "FrostWulf-favicon.png"
TARGET = REPO_ROOT / "assets" / "wulfpack-forge.ico"
ICO_SIZE = 256


def build_ico(source: Path = SOURCE, target: Path = TARGET, size: int = ICO_SIZE) -> bool:
    image = QImage(str(source))
    if image.isNull():
        print(f"Cannot read {source}", file=sys.stderr)
        return False
    scaled = image.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    writer = QImageWriter(str(target), b"ico")
    if not writer.write(scaled):
        print(f"Cannot write {target}: {writer.errorString()}", file=sys.stderr)
        return False
    print(f"Wrote {target} ({scaled.width()}x{scaled.height()})")
    return True


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # Qt needs an application object for pixmaps
    app.setApplicationName("Wulfpack Forge icon builder")
    return 0 if build_ico() else 1


if __name__ == "__main__":
    raise SystemExit(main())
