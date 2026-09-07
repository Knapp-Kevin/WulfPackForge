"""Read-only view of what the character wears and holds, derived from ``equipped`` flags."""
from typing import Dict, List, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QWidget

from data.equipment import hands_for, slot_for
from data.items import resolve_item
from ui.glyphs import item_pixmap

SLOT_ORDER = (
    ("head", "Head"), ("chest", "Chest"), ("legs", "Legs"), ("shoulder", "Cape"),
    ("utility", "Utility"), ("trinket", "Trinket"), ("right", "Right hand"), ("left", "Left hand"),
)
ICON = 40


def _slot_keys(definition) -> List[str]:
    """Panel rows an equipped item occupies: its slot, both hands, one hand, or none."""
    slot, hands = slot_for(definition), hands_for(definition)
    if slot:
        return [slot]
    if hands == "both":
        return ["right", "left"]
    return [hands] if hands else []


def occupants(inventory: List[dict]) -> Dict[str, Optional[dict]]:
    """Which equipped item sits in each slot; the first equipped item wins, nothing is changed."""
    found: Dict[str, Optional[dict]] = {key: None for key, _ in SLOT_ORDER}
    for item in inventory:
        if not item.get("equipped"):
            continue
        for key in _slot_keys(resolve_item(item.get("prefab", ""))):
            found[key] = found[key] or item
    return found


def _display_name(item: dict) -> str:
    definition = resolve_item(item.get("prefab", ""))
    return definition.display_name if definition else item.get("prefab", "?")


class EquipmentPanel(QFrame):
    """Eight labelled rows; ``refresh`` re-derives them from the inventory."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("equipmentPanel")
        self.setStyleSheet(
            "QFrame#equipmentPanel { background-color: #0b1c24; border: 1px solid #284451; border-radius: 7px; }"
            "QLabel { color: #d7e8ee; }"
        )
        layout = QGridLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setHorizontalSpacing(10)
        title = QLabel("Equipped")
        title.setStyleSheet("font-weight: 700; color: #8ad7c1;")
        layout.addWidget(title, 0, 0, 1, 3)
        self._icons: Dict[str, QLabel] = {}
        self._names: Dict[str, QLabel] = {}
        for row, (key, label) in enumerate(SLOT_ORDER, start=1):
            caption = QLabel(label)
            caption.setStyleSheet("color: #a9c1ca;")
            icon = QLabel()
            icon.setFixedSize(QSize(ICON, ICON))
            icon.setAlignment(Qt.AlignCenter)
            name = QLabel("Empty")
            name.setMinimumWidth(150)
            layout.addWidget(caption, row, 0)
            layout.addWidget(icon, row, 1)
            layout.addWidget(name, row, 2)
            self._icons[key] = icon
            self._names[key] = name
        layout.setRowStretch(len(SLOT_ORDER) + 1, 1)

    def refresh(self, inventory: List[dict]) -> None:
        for key, item in occupants(inventory).items():
            if item is None:
                self._icons[key].clear()
                self._names[key].setText("Empty")
                self._names[key].setStyleSheet("color: #5f7480;")
            else:
                self._icons[key].setPixmap(item_pixmap(item.get("prefab", ""), ICON))
                self._names[key].setText(_display_name(item))
                self._names[key].setStyleSheet("color: #d7e8ee;")

    def row_text(self, key: str) -> str:
        return self._names[key].text()
