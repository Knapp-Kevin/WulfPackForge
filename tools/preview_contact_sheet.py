"""Render every hairstyle with one beard into a grid, one PNG per beard, for a person to look at.

The head preview maps each beard onto each hair by their shoulder lines; whether the result looks right
is a judgement only eyes can make, and 38 hairs times 26 beards is too many to click through. This
tool writes one contact sheet per beard so all 988 pairs fit in 26 images. It reads the bundled
thumbnails only and writes nothing outside the folder it is given.
"""
import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from data.appearance import BEARD_NONE, HAIR_NONE, VALHEIM_BEARDS, VALHEIM_HAIRS  # noqa: E402
from ui.appearancePreview import compose_preview  # noqa: E402

SKIN = (0.80, 0.60, 0.50)
HAIR = (0.30, 0.20, 0.10)


def render_sheet(beard: str, hairs: Sequence[str], size: int) -> QImage:
    """One row of previews, ``size`` px each, one column per hair."""
    image = QImage(size * len(hairs), size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    for column, hair in enumerate(hairs):
        painter.drawPixmap(column * size, 0, compose_preview(hair, beard, SKIN, HAIR, 0, size))
    painter.end()
    return image


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Write one hair-by-beard contact sheet per beard.")
    parser.add_argument("--out", required=True, help="folder for the sheet-<beard>.png files")
    parser.add_argument("--size", type=int, default=128, help="pixels per preview (default 128)")
    parser.add_argument("--beard", default=None, help="one beard key, e.g. Beard3 (default: every beard)")
    args = parser.parse_args(argv)
    QApplication.instance() or QApplication([])
    hairs = [key for key in VALHEIM_HAIRS if key != HAIR_NONE]
    beards = [args.beard] if args.beard else [key for key in VALHEIM_BEARDS if key != BEARD_NONE]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for beard in beards:
        render_sheet(beard, hairs, args.size).save(str(out / f"sheet-{beard}.png"))
    print(f"{len(beards)} sheet(s) of {len(hairs)} hairs written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
