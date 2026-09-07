"""Compose a large head preview from the bundled hair and beard thumbnails.

Every thumbnail is split once into a head layer (dark pixels) and a hair layer
(light pixels); both are grey images that keep the original shading. Recolouring
is a multiply composite over those cached layers, so colour changes are instant
and no save field is ever touched.
"""
import math
from typing import Dict, Sequence, Tuple

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from data.appearance import BEARD_NONE, HAIR_NONE, VALHEIM_BEARDS, VALHEIM_HAIRS
from ui.glyphs import glyph_root, placeholder_pixmap, tint_pixmap

PREVIEW_SIZE = 256
HAIR_LIGHTNESS = 88      # HSL lightness at or above this is hair mass; below is head
_HAIR_FULL = 128         # lightness that maps to the full hair colour
_HEAD_FULL = 44          # lightness that maps to the full skin colour
_LAYERS: Dict[Tuple[str, str, int], Tuple[QPixmap, QPixmap]] = {}
_ANCHORS: Dict[Tuple[str, str, int], Tuple[int, int, int]] = {}  # head layer: left, right, bottom
_ANCHOR_ALPHA = 128


def _to_qcolor(rgb: Sequence[float]) -> QColor:
    return QColor(*(int(max(0.0, min(1.0, c)) * 255) for c in rgb[:3]))


def display_color(rgb: Sequence[float]) -> Tuple[QColor, float]:
    """Hue-preserving SDR colour plus the overbright multiplier (1.0 when nothing exceeds 1.0)."""
    safe = [max(0.0, float(c)) for c in rgb[:3]] or [0.0, 0.0, 0.0]
    peak = max(max(safe), 1.0)
    return _to_qcolor([c / peak for c in safe]), peak


def bloom_strength(peak: float) -> float:
    """0 at 1x, about a third at 2x, full at 8x and beyond."""
    return 0.0 if peak <= 1.0 else min(1.0, math.log2(peak) / 3.0)


def _blurred(pixmap: QPixmap, factor: int) -> QPixmap:
    small = pixmap.scaled(max(1, pixmap.width() // factor), max(1, pixmap.height() // factor),
                          Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return small.scaled(pixmap.width(), pixmap.height(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def _bloom(painter: QPainter, tinted: QPixmap, peak: float, x: float = 0.0, y: float = 0.0) -> None:
    """Additive halo around a tinted layer; the multiplier sets how far and how bright it spreads."""
    strength = bloom_strength(peak)
    if strength <= 0.0:
        return
    painter.setCompositionMode(QPainter.CompositionMode_Plus)
    for factor, alpha in ((4, 0.55), (10, 0.45), (24, 0.35)):
        painter.setOpacity(alpha * strength)
        painter.drawPixmap(QRectF(x, y, tinted.width(), tinted.height()), _blurred(tinted, factor),
                           QRectF(0, 0, tinted.width(), tinted.height()))
    painter.setOpacity(1.0)
    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)


def _source(kind: str, key: str, size: int) -> QImage:
    path = glyph_root() / kind / f"{key}.png"
    image = QImage(str(path)) if path.is_file() else QImage()
    if image.isNull():
        return image
    scaled = image.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return scaled.convertToFormat(QImage.Format_ARGB32)


def _grey(level: int, full: int) -> int:
    return min(255, level * 255 // full)


def _split(source: QImage) -> Tuple[QImage, QImage, Tuple[int, int, int]]:
    width, height, stride = source.width(), source.height(), source.bytesPerLine()
    pixels = bytes(source.constBits())
    head, hair = bytearray(len(pixels)), bytearray(len(pixels))
    left, right, bottom = width, 0, 0
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
            left, right, bottom = min(left, x), max(right, x), max(bottom, y)

    def to_image(buf: bytearray) -> QImage:
        return QImage(bytes(buf), width, height, stride, QImage.Format_ARGB32).copy()

    return to_image(head), to_image(hair), (left, right, bottom)


def split_layers(kind: str, key: str, size: int = PREVIEW_SIZE) -> Tuple[QPixmap, QPixmap]:
    """``(head, hair)`` grey layers for one style; both null when no art exists."""
    cache_key = (kind, key, size)
    cached = _LAYERS.get(cache_key)
    if cached is not None:
        return cached
    source = _source(kind, key, size)
    if source.isNull():
        layers = (QPixmap(), QPixmap())
    else:
        head, hair, anchor = _split(source)
        layers = (QPixmap.fromImage(head), QPixmap.fromImage(hair))
        _ANCHORS[cache_key] = anchor
    _LAYERS[cache_key] = layers
    return layers


def beard_transform(hair: str, beard: str, size: int = PREVIEW_SIZE) -> Tuple[float, float, float]:
    """``(scale, dx, dy)`` that maps the beard image's shoulders onto the hair image's shoulders."""
    split_layers("hair", hair, size)
    split_layers("beard", beard, size)
    head_anchor = _ANCHORS.get(("hair", hair, size))
    beard_anchor = _ANCHORS.get(("beard", beard, size))
    if not head_anchor or not beard_anchor or beard_anchor[1] <= beard_anchor[0]:
        return 1.0, 0.0, 0.0
    scale = (head_anchor[1] - head_anchor[0]) / (beard_anchor[1] - beard_anchor[0])
    if beard == BEARD_NONE:
        return 1.0, 0.0, 0.0
    return scale, head_anchor[0] - beard_anchor[0] * scale, head_anchor[2] - beard_anchor[2] * scale


def _draw_centered(painter: QPainter, layer: QPixmap, color: QColor, size: int, peak: float = 1.0) -> None:
    if layer.isNull():
        return
    tinted = tint_pixmap(layer, color)
    x, y = (size - tinted.width()) // 2, (size - tinted.height()) // 2
    painter.drawPixmap(x, y, tinted)
    _bloom(painter, tinted, peak, x, y)


def compose_preview(hair: str, beard: str, skin_rgb: Sequence[float], hair_rgb: Sequence[float],
                    model_index: int, size: int = PREVIEW_SIZE) -> QPixmap:
    """Head with the chosen hair and beard in the chosen colours; beards only on model 0."""
    hair_key = hair if hair in VALHEIM_HAIRS else HAIR_NONE
    beard_key = beard if beard in VALHEIM_BEARDS and model_index == 0 else BEARD_NONE
    head, hair_layer = split_layers("hair", hair_key, size)
    if head.isNull():
        return placeholder_pixmap("?", QColor("#7a8590"), size)
    canvas = QPixmap(size, size)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    (skin, skin_peak), (hair_color, hair_peak) = display_color(skin_rgb), display_color(hair_rgb)
    _draw_centered(painter, head, skin, size, skin_peak)
    _draw_centered(painter, hair_layer, hair_color, size, hair_peak)
    if beard_key != BEARD_NONE:
        _draw_beard(painter, hair_key, beard_key, hair_color, hair_peak, size)
    painter.end()
    return canvas


def _draw_beard(painter, hair_key, beard_key, color, peak, size):
    beard_layer = tint_pixmap(split_layers("beard", beard_key, size)[1], color)
    scale, dx, dy = beard_transform(hair_key, beard_key, size)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    source = QRectF(0, 0, beard_layer.width(), beard_layer.height())
    fitted = beard_layer.scaled(int(beard_layer.width() * scale), int(beard_layer.height() * scale),
                                Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    painter.drawPixmap(QRectF(dx, dy, fitted.width(), fitted.height()), fitted, QRectF(0, 0, fitted.width(), fitted.height()))
    _bloom(painter, fitted, peak, dx, dy)


class ColorSwatch(QWidget):
    """Flat swatch that keeps the hue of an overbright colour and shows the multiplier as a lit rim."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 30)
        self._color, self._peak = QColor("white"), 1.0

    def set_color(self, rgb) -> None:
        self._color, self._peak = display_color(rgb)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(3, 3, -3, -3)
        painter.fillRect(rect, self._color)
        strength = bloom_strength(self._peak)
        if strength > 0.0:
            glow = QColor(self._color)
            for width, alpha in ((6, 0.35), (3, 0.6)):
                glow.setAlphaF(alpha * strength)
                painter.setPen(QPen(glow, width))
                painter.drawRect(rect)
            painter.setCompositionMode(QPainter.CompositionMode_Plus)
            painter.setOpacity(0.5 * strength)
            painter.fillRect(self.rect(), self._color)
        painter.end()


class AppearancePreview(QLabel):
    """Fixed-size label that shows ``compose_preview`` for the current selections."""

    def __init__(self, size: int = PREVIEW_SIZE, parent=None):
        super().__init__(parent)
        self.preview_size = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: #1a1f24; border-radius: 12px;")

    def update_preview(self, hair: str, beard: str, skin_rgb, hair_rgb, model_index: int) -> None:
        self.setPixmap(compose_preview(hair, beard, skin_rgb, hair_rgb, int(model_index or 0), self.preview_size))
