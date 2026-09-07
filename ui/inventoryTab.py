from PySide6.QtWidgets import (
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
        self.main_layout.addWidget(self.usage_hint)
        
        self.slots = {}
        self.init_empty_grid()

    def init_empty_grid(self):
        for i in reversed(range(self.grid_layout.count())): 
            self.grid_layout.itemAt(i).widget().setParent(None)
        
        self.slots.clear()

        for y in range(self.GRID_HEIGHT):
            for x in range(self.GRID_WIDTH):
                slot = InventorySlot(x, y, self)
                slot.setContextMenuPolicy(Qt.CustomContextMenu)
                slot.customContextMenuRequested.connect(lambda pos, s=slot: self.show_slot_menu(pos, s))
                slot.clicked.connect(lambda checked=False, s=slot: self.on_slot_clicked(s))
                
                self.grid_layout.addWidget(slot, y, x)
                self.slots[(x, y)] = slot

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

    def on_slot_clicked(self, slot: InventorySlot):
        """Standard left-click action on a slot."""
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
        dialog = ItemEditDialog(slot.item_data, self)
        result = dialog.exec()
        if result == REMOVE_ITEM:
            self.delete_slot_item(slot)
        elif result == QDialog.Accepted:
            updated = dialog.get_updated_data()
            slot.item_data.update(updated)
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
        if slot.item_data in self.player_data["inventory"]:
            self.player_data["inventory"].remove(slot.item_data)
        slot.clear_item()
        self._refresh_panel()

    def add_item_to_slot(self, slot: InventorySlot):
        picker = ItemPickerDialog(self)
        if picker.exec() != QDialog.Accepted or not picker.selected_prefab:
            return

        new_item = {
            "prefab": picker.selected_prefab,
            "stack": 1,
            "durability": default_durability(picker.selected_prefab),
            "grid_x": slot.grid_x,
            "grid_y": slot.grid_y,
            "equipped": False,
            "quality": 1,
            "variant": 0,
            "crafter_id": 0,
            "crafter_name": "",
            "custom_data": {},
            "world_level": 0,
            "picked_up": True
        }

        dialog = ItemEditDialog(new_item, self)
        if dialog.exec() == QDialog.Accepted:
            final_item = dialog.get_updated_data()
            new_item.update(final_item)
            
            self.player_data["inventory"].append(new_item)
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
