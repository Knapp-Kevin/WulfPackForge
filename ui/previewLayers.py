"""Split a thumbnail into head and hair layers and find its shoulder line.

Every hair or beard thumbnail is a render of the same bust: a head with hair or a beard on top of
neck and shoulders. Dark pixels are skin, light pixels are hair. The **shoulder line**, the first
row whose dark width reaches 90 percent of the widest dark row, is the one feature both kinds of
thumbnail share at the same place on the bust, so the head preview maps a beard onto a hairstyle
by their shoulder lines (phase 47). Beard thumbnails also carry a light highlight on the bald
crown; it is masked out here so it is never tinted and drawn over the hair.
"""
from typing import Dict, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter

HAIR_LIGHTNESS = 88      # HSL lightness at or above this is hair mass; below is head
_HAIR_FULL = 128         # lightness that maps to the full hair colour
_HEAD_FULL = 44          # lightness that maps to the full skin colour
_ANCHOR_ALPHA = 128
_SHOULDER_FRACTION = 0.9  # a row this wide, relative to the widest, is where the shoulders begin
_CROWN_LIMIT = 0.45       # a light run ending above this fraction of the height is the crown highlight

Rows = Dict[int, Tuple[int, int]]


def _grey(level: int, full: int) -> int:
    return min(255, level * 255 // full)


def _split(source: QImage) -> Tuple[QImage, QImage, Rows]:
    """Head and hair layers plus, per row, the leftmost and rightmost dark pixel."""
    width, height, stride = source.width(), source.height(), source.bytesPerLine()
    pixels = bytes(source.constBits())
    head, hair = bytearray(len(pixels)), bytearray(len(pixels))
    rows: Rows = {}
    for i in range(0, len(pixels), 4):
        b, g, r, a = pixels[i:i + 4]
        if a == 0:
            continue
        lightness = (max(r, g, b) + min(r, g, b)) // 2
        is_hair = lightness >= HAIR_LIGHTNESS
        target, full = (hair, _HAIR_FULL) if is_hair else (head, _HEAD_FULL)
        grey = _grey(lightness, full)
        target[i:i + 4] = bytes((grey, grey, grey, a))
        if not is_hair and a > _ANCHOR_ALPHA:
            x, y = (i // 4) % (stride // 4), (i // 4) // (stride // 4)
            low, high = rows.get(y, (x, x))
            rows[y] = (min(low, x), max(high, x))

    def to_image(buf: bytearray) -> QImage:
        # Copy into a Qt-owned image: constructing a QImage over a Python buffer leaves Qt with a
        # pointer into memory Python may free, which corrupts the heap silently.
        image = QImage(width, height, QImage.Format_ARGB32)
        image.bits()[:len(buf)] = bytes(buf)
        return image

    return to_image(head), to_image(hair), rows


def _anchor(rows: Rows, height: int) -> Tuple[int, int, int, int]:
    """``(left, right, top, bottom)``: the dark extents, the shoulder line, and the lowest dark row."""
    if not rows:
        return 0, 0, 0, 0
    widest = max(high - low for low, high in rows.values())
    top = min(y for y, (low, high) in rows.items() if high - low >= _SHOULDER_FRACTION * widest)
    return min(low for low, _ in rows.values()), max(high for _, high in rows.values()), top, max(rows)


def _light_runs(layer: QImage) -> List[Tuple[int, int]]:
    """``(first, last)`` row of every run of consecutive rows holding a pixel with alpha above the anchor threshold."""
    stride, pixels = layer.bytesPerLine(), bytes(layer.constBits())
    opaque = sorted({(i // 4) // (stride // 4) for i in range(3, len(pixels), 4) if pixels[i] > _ANCHOR_ALPHA})
    runs: List[List[int]] = []
    for y in opaque:
        if runs and y == runs[-1][1] + 1:
            runs[-1][1] = y
        else:
            runs.append([y, y])
    return [(first, last) for first, last in runs]


def _without_crown(layer: QImage, height: int) -> QImage:
    """The layer with every light run that ends above the crown limit cleared."""
    crown = [run for run in _light_runs(layer) if run[1] < _CROWN_LIMIT * height]
    if not crown:
        return layer
    painter = QPainter(layer)
    painter.setCompositionMode(QPainter.CompositionMode_Clear)
    for first, last in crown:
        painter.fillRect(0, first, layer.width(), last - first + 1, Qt.transparent)
    painter.end()
    return layer
