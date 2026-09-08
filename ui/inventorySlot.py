from PySide6.QtCore import QMimeData, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QDrag, QIcon, QPainter
from PySide6.QtWidgets import QApplication, QToolButton

from data.equipment import role_for, slot_for
from data.items import resolve_item
from ui.glyphs import item_icon

SLOT_MIME = "application/x-wulfpack-slot"
SLOT_SIZE = QSize(128, 140)
ICON_SIZE = 84


class InventorySlot(QToolButton):
    """One inventory grid tile: icon, name, stack and quality badges, drag source and drop target."""

    def __init__(self, x, y, parent=None):
        super().__init__(parent)
        self.grid_x = x
        self.grid_y = y
        self.item_data = None
        self._press_pos = None
        self.setFixedSize(SLOT_SIZE)
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setAcceptDrops(True)
        self.update_visuals()

    def set_item(self, item_data):
        self.item_data = item_data
        self.update_visuals()

    def clear_item(self):
        self.item_data = None
        self.update_visuals()

    def update_visuals(self):
        if self.item_data:
            self._show_item()
        else:
            self.setIcon(QIcon())
            self.setText(f"({self.grid_x}, {self.grid_y})")
            self.setAccessibleName(f"Empty inventory slot {self.grid_x}, {self.grid_y}")
            self.setToolTip("Empty inventory slot")
            self.setStyleSheet("background-color: #1a1a1a; color: #444444; border: 1px dashed #333333;")
        self.update()

    def _show_item(self):
        prefab = self.item_data.get("prefab", "Unknown")
        stack = self.item_data.get("stack", 1)
        is_equipped = self.item_data.get("equipped", False)
        catalog_item = resolve_item(prefab)
        display_name = catalog_item.display_name if catalog_item else prefab.replace("$item_", "").replace("_", " ").title()

        self.setIcon(item_icon(prefab, ICON_SIZE, int(self.item_data.get("variant", 0) or 0)))
        self.setText(display_name)
        state = "equipped" if is_equipped else "not equipped"
        self.setAccessibleName(f"{display_name}, stack {stack}, {state}")
        role, slot = role_for(catalog_item), slot_for(catalog_item)
        role_line = f"Role: {role}\n" if role != "none" else ""
        slot_line = f"Slot: {slot}\n" if slot else ""
        self.setToolTip(
            f"Prefab: {prefab}\nItem: {display_name}\n{role_line}{slot_line}"
            f"Equipped: {'Yes' if is_equipped else 'No'}\n"
            f"Quality: {self.item_data.get('quality', 1)}\nVariant: {self.item_data.get('variant', 0)}\n"
            "Drag to another slot to move or swap"
        )
        if is_equipped:
            self.setStyleSheet("background-color: #3a4d22; color: white; border: 2px solid #9acd32; font-weight: bold;")
        else:
            self.setStyleSheet("background-color: #3e2723; color: #d7ccc8; border: 1px solid #5d4037;")

    # ------------------------------------------------------------------ badges
    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.item_data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        stack = self.item_data.get("stack", 1)
        if stack > 1:
            self._badge(painter, f"x{stack}", QColor("#c9d2dc"), QColor("#1a1f24"), top_right=True)
        quality = self.item_data.get("quality", 1)
        if quality > 1:
            self._badge(painter, f"Q{quality}", QColor("#f0c878"), QColor("#1a1f24"), top_right=False)
        painter.end()

    def _badge(self, painter, text, fill, ink, top_right):
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(text) + 10
        height = metrics.height() + 2
        x = self.width() - width - 5 if top_right else 5
        rect = QRect(x, 5, width, height)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(ink)
        painter.drawText(rect, Qt.AlignCenter, text)

    def keyPressEvent(self, event):
        parent = self.parent()
        if self.item_data and event.key() in (Qt.Key_Delete, Qt.Key_Backspace) and hasattr(parent, "delete_slot_item"):
            parent.delete_slot_item(self)
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------ drag/drop
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self.item_data and self._press_pos is not None and event.buttons() & Qt.LeftButton
                and (event.position().toPoint() - self._press_pos).manhattanLength() >= QApplication.startDragDistance()):
            self._press_pos = None
            self.setDown(False)
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(SLOT_MIME, f"{self.grid_x},{self.grid_y}".encode("ascii"))
            drag.setMimeData(mime)
            drag.setPixmap(self.icon().pixmap(ICON_SIZE, ICON_SIZE))
            drag.setHotSpot(QPoint(ICON_SIZE // 2, ICON_SIZE // 2))
            drag.exec(Qt.MoveAction)
            return
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(SLOT_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(SLOT_MIME):
            event.acceptProposedAction()

    def dropEvent(self, event):
        raw = bytes(event.mimeData().data(SLOT_MIME)).decode("ascii", "ignore")
        try:
            sx, sy = (int(part) for part in raw.split(","))
        except ValueError:
            event.ignore()
            return
        owner = self.parent()
        if owner is not None and hasattr(owner, "move_item") and owner.move_item((sx, sy), (self.grid_x, self.grid_y)):
            event.acceptProposedAction()
        else:
            event.ignore()
