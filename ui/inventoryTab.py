from PySide6.QtWidgets import (
    QPushButton,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QDialog
)

from PySide6.QtCore import Qt

from data.durability import default_durability
from data.equipment import resolve_equip
from data.items import resolve_item
from ui.equipmentPanel import EquipmentPanel
from ui.inventorySlot import InventorySlot
from ui.itemEditDialog import REMOVE_ITEM, ItemEditDialog
from ui.itemPickerDialog import ItemPickerDialog
from ui.iconExtractionDialog import IconExtractionDialog
from ui.lifetime import modal
from subscripts.playerDataUtil import new_inventory_item
from ui.glyphs import clear_cache

class InventoryTab(QWidget):
    GRID_WIDTH = 8
    GRID_HEIGHT = 4

    def __init__(self):
        super().__init__()
        self.player_data = None
        
        self.main_layout = QVBoxLayout(self)
        body = QHBoxLayout()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(8)
        body.addLayout(self.grid_layout)
        self.equipment_panel = EquipmentPanel()
        body.addWidget(self.equipment_panel, 0, Qt.AlignTop)
        body.addStretch(1)
        self.main_layout.addLayout(body)
        self.equip_status = QLabel()
        self.equip_status.setWordWrap(True)
        self.equip_status.setStyleSheet("color: #c4d8df;")
        self.main_layout.addWidget(self.equip_status)
        self.usage_hint = QLabel(
            "Left-click a slot to edit it or add an item. Right-click for the menu. Drag an item to move or swap it. "
            "Press Delete on a slot, or use Remove from Inventory in the editor, to take an item out."
        )
        self.usage_hint.setWordWrap(True)
        self.usage_hint.setStyleSheet("color: #8fa3ab;")
        footer = QHBoxLayout()
        footer.addWidget(self.usage_hint, 1)
        self.btn_game_icons = QPushButton("Game Icons…")
        self.btn_game_icons.setToolTip("Read the item icons from your own Valheim installation (optional)")
        self.btn_game_icons.clicked.connect(self.open_game_icons)
        footer.addWidget(self.btn_game_icons, 0, Qt.AlignTop)
        self.main_layout.addLayout(footer)
        
        self.slots = {}
        self.init_empty_grid()

    def init_empty_grid(self):
        # takeAt transfers the layout item to us; the previous form, itemAt(i).widget().setParent(None),
        # left it owned by the layout while we reparented its widget, and caused a native crash that
        # surfaced much later in an unrelated dialog. Measured: 5 of 6 runs crashed before, 0 of 6 after.
        # Why exactly it corrupted state is unresolved; see docs/plan-qor-phase40-layout-item-uaf.md.
        while self.grid_layout.count():
            taken = self.grid_layout.takeAt(0)
            widget = taken.widget()
            if widget is not None:
                widget.setParent(None)
        self.slots.clear()

        for y in range(self.GRID_HEIGHT):
            for x in range(self.GRID_WIDTH):
                slot = InventorySlot(x, y, self)
                slot.setContextMenuPolicy(Qt.CustomContextMenu)
                slot.customContextMenuRequested.connect(self._slot_menu_requested)
                slot.clicked.connect(self._slot_clicked)
                
                self.grid_layout.addWidget(slot, y, x)
                self.slots[(x, y)] = slot

    def open_game_icons(self):
        with modal(IconExtractionDialog(self)) as dialog:
            dialog.extracted.connect(self._icons_extracted)
            dialog.exec()
            dialog.shutdown()

    def _icons_extracted(self, _report):
        clear_cache()
        for slot in self.slots.values():
            if slot.item_data:
                slot.set_item(slot.item_data)

    def load_data(self, player_data):
        self.player_data = player_data
        self.equip_status.setText("")
        self.init_empty_grid()

        inventory_list = player_data.get("inventory", [])
        for item in inventory_list:
            x = item.get("grid_x", 0)
            y = item.get("grid_y", 0)
            if (x, y) in self.slots:
                self.slots[(x, y)].set_item(item)
        self.equipment_panel.refresh(inventory_list)

    def _slot_clicked(self, _checked=False):
        self.on_slot_clicked(self.sender())

    def _slot_menu_requested(self, position):
        self.show_slot_menu(position, self.sender())

    def on_slot_clicked(self, slot: InventorySlot):
        """Standard left-click action on a slot."""
        if not self.player_data:
            return
        if slot.item_data:
            self.edit_slot_item(slot)
        else:
            self.add_item_to_slot(slot)

    def show_slot_menu(self, position, slot: InventorySlot):
        """Right-click context menu options."""
        menu = QMenu()
        
        if slot.item_data:
            edit_action = menu.addAction("Edit Item")
            delete_action = menu.addAction("Delete/Empty Slot")
            action = menu.exec(slot.mapToGlobal(position))
            
            if action == edit_action:
                self.edit_slot_item(slot)
            elif action == delete_action:
                self.delete_slot_item(slot)
        else:
            add_action = menu.addAction("Add Item Here")
            action = menu.exec(slot.mapToGlobal(position))
            
            if action == add_action:
                self.add_item_to_slot(slot)

    def edit_slot_item(self, slot: InventorySlot):
        if not self.player_data or not slot.item_data:
            return
        with modal(ItemEditDialog(slot.item_data, self)) as dialog:
            result = dialog.exec()
            if result == REMOVE_ITEM:
                self.delete_slot_item(slot)
            elif result == QDialog.Accepted:
                slot.item_data.update(dialog.get_updated_data())
                slot.update_visuals()
                self._enforce_equip_rule(slot.item_data)
                self._refresh_panel()

    def delete_slot_item(self, slot: InventorySlot, confirm: bool = True):
        """Take the slot's item out of the inventory; every removal path ends here."""
        if not slot.item_data or not self.player_data:
            return
        if confirm:
            item = resolve_item(slot.item_data.get("prefab", ""))
            name = item.display_name if item else slot.item_data.get("prefab", "this item")
            answer = QMessageBox.question(
                self, "Remove Item",
                f"Remove {name} ({slot.item_data.get('prefab', '')}) from slot ({slot.grid_x}, {slot.grid_y})?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        inventory = self.player_data.setdefault("inventory", [])
        if slot.item_data in inventory:
            inventory.remove(slot.item_data)
        slot.clear_item()
        self._refresh_panel()

    def add_item_to_slot(self, slot: InventorySlot):
        if not self.player_data:
            return
        with modal(ItemPickerDialog(self)) as picker:
            accepted = picker.exec() == QDialog.Accepted
            prefab = picker.selected_prefab
        if not accepted or not prefab:
            return

        new_item = new_inventory_item(prefab, slot.grid_x, slot.grid_y, default_durability(prefab))
        with modal(ItemEditDialog(new_item, self)) as dialog:
            if dialog.exec() != QDialog.Accepted:
                return
            new_item.update(dialog.get_updated_data())
        self.player_data.setdefault("inventory", []).append(new_item)
        slot.set_item(new_item)
        self._enforce_equip_rule(new_item)
        self._refresh_panel()

    def _refresh_panel(self):
        if self.player_data is not None:
            self.equipment_panel.refresh(self.player_data.get("inventory", []))

    def move_item(self, source, target) -> bool:
        """Move the item in ``source`` to ``target``, swapping when ``target`` is occupied.

        Only ``grid_x``/``grid_y`` of the items involved change. Slots outside the
        visible grid are never touched.
        """
        source, target = tuple(source), tuple(target)
        if source == target or source not in self.slots or target not in self.slots:
            return False
        moving = self.slots[source].item_data
        if moving is None:
            return False
        displaced = self.slots[target].item_data
        moving["grid_x"], moving["grid_y"] = target
        if displaced is not None:
            displaced["grid_x"], displaced["grid_y"] = source
        self.slots[target].set_item(moving)
        if displaced is not None:
            self.slots[source].set_item(displaced)
        else:
            self.slots[source].clear_item()
        self._refresh_panel()
        return True

    def _enforce_equip_rule(self, item):
        """Mirror the game: one item per slot, hands exclusive with two-handed items."""
        changed = resolve_equip(self.player_data.get("inventory", []), item)
        if not changed:
            return
        for other in changed:
            slot = self.slots.get((other.get("grid_x"), other.get("grid_y")))
            if slot is not None and slot.item_data is other:
                slot.update_visuals()
        names = []
        for other in changed:
            catalog = resolve_item(other.get("prefab", ""))
            names.append(catalog.display_name if catalog else other.get("prefab", "?"))
        self.equip_status.setText("Unequipped to make room: " + ", ".join(names))

    def save_changes(self):
        """Nothing to collect: every edit mutates the item dictionaries inside ``player_data`` in place."""
