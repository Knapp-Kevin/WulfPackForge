"""Render inventory icons: a tinted glyph master when present, else a drawn placeholder."""
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QImageReader, QPainter, QPixmap

from data.appearance import VALHEIM_BEARDS, VALHEIM_HAIRS
from data.glyphs import GLYPH_IDS, GLYPH_MASTER_DIR, TINTS, glyph_for
from data.items import ItemDefinition, resolve_item
from subscripts.iconExtraction import cached_icon_path, icon_cache_dir
from subscripts.modOverride import mod_icons_dir
from subscripts.workspace import default_workspace_root
from ui.branding import resource_path

# Two key widths are in use: (label, tint, size) and ("extracted", prefab, size, variant).
_CACHE: Dict[Tuple[Union[str, int], ...], QPixmap] = {}
GLYPH_MASTER_SIZE = 512


def clear_cache() -> None:
    _CACHE.clear()


def glyph_root() -> Path:
    return resource_path("assets/glyphs")


def master_dir() -> Path:
    return resource_path(GLYPH_MASTER_DIR)


def appearance_pixmap(kind: str, key: str, size: int = 48) -> QPixmap:
    """Thumbnail for a hair or beard entry, or a null pixmap when no art exists."""
    cache_key = (f"{kind}:{key}", "none", size)
    cached = _CACHE.get(cache_key)
    if cached is not None:
        return cached
    path = glyph_root() / kind / f"{key}.png"
    pixmap = QPixmap(str(path)) if path.is_file() else QPixmap()
    if not pixmap.isNull():
        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    _CACHE[cache_key] = pixmap
    return pixmap


def populate_appearance_combo(combo, table: Dict[str, str], kind: str) -> None:
    """Fill a combo with ``{key: label}`` entries, attaching thumbnails where art exists."""
    combo.clear()
    for key, label in table.items():
        pixmap = appearance_pixmap(kind, key)
        if pixmap.isNull():
            combo.addItem(label, key)
        else:
            combo.addItem(QIcon(pixmap), label, key)


def tint_pixmap(pixmap: QPixmap, color: QColor) -> QPixmap:
    """Multiply the pixmap by ``color`` while keeping its original alpha."""
    result = QPixmap(pixmap.size())
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_Multiply)
    painter.fillRect(result.rect(), color)
    painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return result


def placeholder_pixmap(label: str, color: QColor, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor("#1a1f24"))
    painter.setBrush(color)
    radius = size * 0.18
    painter.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), radius, radius)
    font = QFont()
    font.setBold(True)
    font.setPixelSize(int(size * 0.38))
    painter.setFont(font)
    painter.setPen(QColor("#f4f7f9") if color.lightness() < 150 else QColor("#1a1f24"))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, label)
    painter.end()
    return pixmap


def _label_for(item: Optional[ItemDefinition], prefab: str) -> str:
    words = (item.display_name if item else prefab).replace("_", " ").split()
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return (words[0][:2] if words else "?").upper()


def extracted_pixmap(prefab: str, size: int, variant: int = 0) -> Optional[QPixmap]:
    """An icon the user extracted from their own game into the workspace, or None; per style when known."""
    key = ("extracted", prefab, size, variant)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    path = cached_icon_path(icon_cache_dir(default_workspace_root()), prefab, variant)
    if path is None and mod_icons_dir() is not None:
        path = cached_icon_path(mod_icons_dir(), prefab, variant)
    if path is None:
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    _CACHE[key] = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return _CACHE[key]


def item_pixmap(target: Union[str, ItemDefinition], size: int = 64, variant: int = 0) -> QPixmap:
    item = target if isinstance(target, ItemDefinition) else resolve_item(target)
    prefab = item.prefab if item else str(target)
    extracted = extracted_pixmap(prefab, size, variant)
    if extracted is not None:
        return extracted
    glyph, tint = glyph_for(item)
    key = (glyph if item else f"placeholder:{prefab}", tint, size)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    color = QColor(TINTS[tint])
    master = master_dir() / f"{glyph}.png"
    if master.is_file() and not QPixmap(str(master)).isNull():
        pixmap = tint_pixmap(
            QPixmap(str(master)).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation), color
        )
    else:
        pixmap = placeholder_pixmap(_label_for(item, prefab), color, size)
    _CACHE[key] = pixmap
    return pixmap


def item_icon(target: Union[str, ItemDefinition], size: int = 64, variant: int = 0) -> QIcon:
    return QIcon(item_pixmap(target, size, variant))


def glyph_bundle_is_usable() -> bool:
    """Check objective runtime requirements without pretending CI can judge art."""
    if not GLYPH_IDS or len(set(GLYPH_IDS)) != len(GLYPH_IDS):
        return False

    for glyph_id in GLYPH_IDS:
        path = master_dir() / f"{glyph_id}.png"
        if not path.is_file():
            return False
        reader = QImageReader(str(path))
        if not reader.canRead():
            return False
        image = reader.read()
        if (
            image.isNull()
            or image.width() != GLYPH_MASTER_SIZE
            or image.height() != GLYPH_MASTER_SIZE
            or not image.hasAlphaChannel()
        ):
            return False
    return True


def appearance_bundle_is_usable() -> bool:
    """Verify every catalog hair and beard thumbnail is present and decodable."""
    catalogs = (("hair", VALHEIM_HAIRS), ("beard", VALHEIM_BEARDS))
    for kind, entries in catalogs:
        for key in entries:
            reader = QImageReader(str(glyph_root() / kind / f"{key}.png"))
            if not reader.canRead():
                return False
            image = reader.read()
            if image.isNull() or image.size().width() != 512 or image.size().height() != 512:
                return False
    return True
