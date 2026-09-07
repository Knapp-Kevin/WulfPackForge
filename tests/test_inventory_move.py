import copy
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from subscripts.playerDataUtil import unpack_player_data_hex
from tests.fixture_saves import realistic_player_hex
from ui.equipmentPanel import EquipmentPanel, occupants
from ui.inventoryTab import InventoryTab


APP = QApplication.instance() or QApplication([])


def base_item(prefab, x, y, equipped=False):
    return {"prefab": prefab, "stack": 1, "durability": 100.0, "grid_x": x, "grid_y": y, "equipped": equipped,
            "quality": 1, "variant": 0, "crafter_id": 0, "crafter_name": "", "custom_data": {},
            "world_level": 0, "picked_up": True}


def fixture():
    return unpack_player_data_hex(realistic_player_hex())


class MoveItemTests(unittest.TestCase):
    def test_move_to_empty_slot_changes_only_coordinates(self):
        data = fixture()
        before = copy.deepcopy(data)
        tab = InventoryTab()
        tab.load_data(data)
        sword = data["inventory"][0]

        self.assertTrue(tab.move_item((0, 0), (5, 3)))
        self.assertEqual((sword["grid_x"], sword["grid_y"]), (5, 3))
        self.assertIs(tab.slots[(5, 3)].item_data, sword)
        self.assertIsNone(tab.slots[(0, 0)].item_data)
        for key, value in before["inventory"][0].items():
            if key not in ("grid_x", "grid_y"):
                self.assertEqual(sword[key], value, key)
        self.assertEqual(data["inventory"][1:], before["inventory"][1:])

    def test_move_onto_occupied_slot_swaps(self):
        data = fixture()
        tab = InventoryTab()
        tab.load_data(data)
        sword, wood = data["inventory"][0], data["inventory"][1]
        self.assertTrue(tab.move_item((0, 0), (3, 1)))
        self.assertEqual((sword["grid_x"], sword["grid_y"]), (3, 1))
        self.assertEqual((wood["grid_x"], wood["grid_y"]), (0, 0))
        self.assertIs(tab.slots[(0, 0)].item_data, wood)

    def test_noop_and_offgrid_items_untouched(self):
        data = fixture()
        before = copy.deepcopy(data)
        tab = InventoryTab()
        tab.load_data(data)
        self.assertFalse(tab.move_item((0, 0), (0, 0)))
        self.assertFalse(tab.move_item((5, 3), (6, 3)))
        self.assertEqual(data, before)
        tab.move_item((0, 0), (1, 1))
        self.assertEqual(data["inventory"][2], before["inventory"][2])  # off-grid backpack item


class EquipmentPanelTests(unittest.TestCase):
    def test_occupants_by_slot_and_hands(self):
        inventory = [
            base_item("ArmorFenringChest", 0, 0, True), base_item("Bow", 1, 0, True),
            base_item("ShieldWood", 2, 0, True), base_item("Wood", 3, 0, False),
        ]
        found = occupants(inventory)
        self.assertEqual(found["chest"]["prefab"], "ArmorFenringChest")
        self.assertEqual(found["right"]["prefab"], "Bow")
        self.assertEqual(found["left"]["prefab"], "Bow")
        self.assertIsNone(found["head"])
        self.assertEqual(set(found), {"head", "chest", "legs", "shoulder", "utility", "trinket", "right", "left"})

    def test_equipment_panel_shows_worn_items(self):
        data = fixture()
        data["inventory"].append(base_item("ArmorFenringChest", 4, 0, True))
        before = copy.deepcopy(data)
        tab = InventoryTab()
        tab.load_data(data)
        self.assertEqual(tab.equipment_panel.row_text("chest"), "Fenris Coat")
        self.assertEqual(tab.equipment_panel.row_text("head"), "Empty")
        self.assertEqual(tab.equipment_panel.row_text("right"), "Bronze Sword")
        self.assertEqual(data, before)  # the panel never writes

        chest_slot = tab.slots[(4, 0)]
        tab.player_data["inventory"].remove(chest_slot.item_data)
        chest_slot.clear_item()
        tab.equipment_panel.refresh(tab.player_data["inventory"])
        self.assertEqual(tab.equipment_panel.row_text("chest"), "Empty")

    def test_panel_is_standalone_widget(self):
        panel = EquipmentPanel()
        panel.refresh([])
        self.assertEqual(panel.row_text("left"), "Empty")


if __name__ == "__main__":
    unittest.main()
