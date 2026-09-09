"""Choose an item style by picture: a combo of the variant icons with an approximate colour name."""
from typing import List

from PySide6.QtCore import QObject, QSize, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap

from subscripts.variantIcons import variant_icon_paths

ICON_SIZE = 40
HUE_NAMES = ((15, "red"), (45, "orange"), (70, "yellow"), (165, "green"), (195, "teal"), (255, "blue"), (290, "purple"),
             (345, "pink"), (361, "red"))


def average_colour(image: QImage) -> QColor:
    """Mean of the opaque pixels; transparent black when the image has none."""
    total = [0, 0, 0]
    count = 0
    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            if pixel.alpha() < 128:
                continue
            total[0] += pixel.red()
            total[1] += pixel.green()
            total[2] += pixel.blue()
            count += 1
    if not count:
        return QColor(0, 0, 0, 0)
    return QColor(total[0] // count, total[1] // count, total[2] // count)


def colour_name(colour: QColor) -> str:
    """A rough, human colour word for a swatch: grey scale by lightness, else by hue."""
    if colour.alpha() == 0:
        return "unknown"
    hue, saturation, value = colour.hsvHueF() * 360, colour.hsvSaturationF(), colour.valueF()
    if saturation < 0.18:
        if value < 0.25:
            return "black"
        return "white" if value > 0.8 else "grey"
    name = next(label for limit, label in HUE_NAMES if hue < limit)
    if name in ("orange", "yellow", "red") and value < 0.55:
        return "brown"
    return name


def variant_choices(prefab: str) -> List[tuple]:
    """``[(index, label, pixmap), ...]`` for each extracted style icon, or an empty list."""
    choices = []
    for index, path in enumerate(variant_icon_paths(prefab)):
        image = QImage(str(path))
        if image.isNull():
            continue
        label = f"Style {index} · {colour_name(average_colour(image))}"
        choices.append((index, label, QPixmap.fromImage(image)))
    return choices


def populate_variant_combo(combo, prefab: str) -> int:
    """Fill a combo with the style icons for ``prefab``; returns how many styles it offers."""
    combo.clear()
    combo.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
    for index, label, pixmap in variant_choices(prefab):
        combo.addItem(QIcon(pixmap.scaled(ICON_SIZE, ICON_SIZE)), label, index)
    return combo.count()



class StyleSync(QObject):
    """Keeps a style combo and the numeric variant field in step; ``changed`` fires on either.

    The value travels out through a Qt signal rather than a stored callback. A callback held as
    a plain attribute closes a ``dialog -> sync -> dialog`` reference cycle, which reference
    counting cannot break, so the owning dialog would be freed by the cyclic collector at a
    moment of Python's choosing instead of when its last reference goes.
    """

    changed = Signal(int)

    def __init__(self, combo, spin):
        super().__init__(combo)
        self.combo, self.spin = combo, spin
        combo.currentIndexChanged.connect(self._style_chosen)
        spin.valueChanged.connect(self._variant_typed)

    def refresh(self, prefab: str) -> None:
        self.combo.blockSignals(True)
        count = populate_variant_combo(self.combo, prefab)
        self.combo.setCurrentIndex(self.combo.findData(self.spin.value()))
        self.combo.blockSignals(False)
        self.combo.setVisible(count > 0)

    def _style_chosen(self, index: int) -> None:
        if index >= 0 and self.combo.itemData(index) is not None:
            self.spin.setValue(int(self.combo.itemData(index)))

    def _variant_typed(self, value: int) -> None:
        position = self.combo.findData(value)
        if position != self.combo.currentIndex():
            self.combo.setCurrentIndex(position)
        self.changed.emit(value)
