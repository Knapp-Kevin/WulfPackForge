"""Categorised item picker: a navigation tree on the left, an icon grid on the right."""
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from data.equipment import role_for, slot_for
from data.item_groups import GROUPS, items_under, material_for, navigation_tree, pickable_items
from ui.glyphs import item_icon

ADVANCED = "Advanced"
ICON_SIZE = 96
CELL = QSize(150, 150)
NODE_ROLE = Qt.UserRole


class ItemPickerDialog(QDialog):
    """Pick a catalog item by category, subtype, and material, by search, or by raw prefab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Item")
        self.resize(860, 540)
        self.selected_prefab: Optional[str] = None
        self._current_node = (GROUPS[0], None, None)

        layout = QHBoxLayout(self)

        self.categories = QTreeWidget()
        self.categories.setHeaderHidden(True)
        self.categories.setFixedWidth(210)
        self._build_tree()
        layout.addWidget(self.categories)

        layout.addLayout(self._build_right_pane(), 1)

        self.categories.currentItemChanged.connect(self._node_changed)
        self.search.textChanged.connect(self._apply_search)
        self.grid.itemDoubleClicked.connect(self._tile_double_clicked)
        self.categories.setCurrentItem(self.categories.topLevelItem(0))

    def _build_right_pane(self) -> QVBoxLayout:
        right = QVBoxLayout()
        self.breadcrumb = QLabel(GROUPS[0])
        self.breadcrumb.setStyleSheet("font-weight: 600; color: #8ad7c1;")
        right.addWidget(self.breadcrumb)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search all items by name or prefab")
        right.addWidget(self.search)
        self.pages = QStackedWidget()
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.IconMode)
        self.grid.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.grid.setGridSize(CELL)
        self.grid.setResizeMode(QListWidget.Adjust)
        self.grid.setWrapping(True)
        self.grid.setUniformItemSizes(True)
        self.grid.setWordWrap(True)
        self.pages.addWidget(self.grid)
        self.pages.addWidget(self._build_advanced_page())
        right.addWidget(self.pages, 1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        right.addWidget(self.buttons)
        return right

    def _build_advanced_page(self) -> QWidget:
        advanced = QWidget()
        advanced_layout = QVBoxLayout(advanced)
        advanced_layout.addWidget(QLabel(
            "Enter a raw prefab ID for a modded item or an item newer than the bundled catalog. "
            "The value is written exactly as typed."
        ))
        self.raw_input = QLineEdit()
        self.raw_input.setPlaceholderText("Prefab ID")
        advanced_layout.addWidget(self.raw_input)
        advanced_layout.addStretch()
        return advanced

    def _build_tree(self) -> None:
        for group, branches in navigation_tree():
            top = QTreeWidgetItem([f"{group} ({len(items_under(group))})"])
            top.setData(0, NODE_ROLE, (group, None, None))
            for subgroup, materials in branches:
                child = QTreeWidgetItem([f"{subgroup} ({len(items_under(group, subgroup))})"])
                child.setData(0, NODE_ROLE, (group, subgroup, None))
                for material in materials:
                    leaf = QTreeWidgetItem([f"{material} ({len(items_under(group, subgroup, material))})"])
                    leaf.setData(0, NODE_ROLE, (group, subgroup, material))
                    child.addChild(leaf)
                top.addChild(child)
            self.categories.addTopLevelItem(top)
        advanced = QTreeWidgetItem([ADVANCED])
        advanced.setData(0, NODE_ROLE, (ADVANCED, None, None))
        self.categories.addTopLevelItem(advanced)

    def select_group(self, name: str) -> None:
        for index in range(self.categories.topLevelItemCount()):
            top = self.categories.topLevelItem(index)
            if top.data(0, NODE_ROLE)[0] == name:
                self.categories.setCurrentItem(top)
                return

    def _node_changed(self, current, _previous=None) -> None:
        if current is None:
            return
        node = current.data(0, NODE_ROLE)
        if node[0] == ADVANCED:
            self.pages.setCurrentIndex(1)
            self.raw_input.setFocus()
            return
        self._current_node = node
        self.breadcrumb.setText(" › ".join(part for part in node if part))
        self.pages.setCurrentIndex(0)
        if self.search.text().strip():
            self._apply_search(self.search.text())
        else:
            self._fill(items_under(*node))

    def _apply_search(self, text: str) -> None:
        needle = text.strip().lower()
        if not needle:
            self._fill(items_under(*self._current_node))
            return
        if self.pages.currentIndex() != 0:
            self.pages.setCurrentIndex(0)
        self._fill(item for item in pickable_items()
                   if needle in item.display_name.lower() or needle in item.prefab.lower())

    def _fill(self, items) -> None:
        self.grid.clear()
        for item in items:
            material = material_for(item)
            label = f"{item.display_name}\n{material}" if material else item.display_name
            row = QListWidgetItem(item_icon(item, ICON_SIZE), label)
            row.setData(Qt.UserRole, item.prefab)
            row.setToolTip(_describe(item))
            row.setSizeHint(QSize(140, 146))
            self.grid.addItem(row)

    def _tile_double_clicked(self, _item):
        self.accept()

    def accept(self) -> None:
        if self.pages.currentIndex() == 1:
            raw = self.raw_input.text().strip()
            if not raw:
                return
            self.selected_prefab = raw
        else:
            current = self.grid.currentItem()
            if current is None:
                return
            self.selected_prefab = current.data(Qt.UserRole)
        super().accept()


def _describe(item) -> str:
    role = role_for(item)
    lines = [item.display_name, f"Prefab: {item.prefab}", f"Type: {item.item_type or 'unknown'}"]
    if role == "creature":
        lines.append("Creature gear: not wearable by players")
    elif role != "none":
        lines.append(f"Role: {role}")
    slot = slot_for(item)
    if slot:
        lines.append(f"Slot: {slot}")
    return "\n".join(lines)
