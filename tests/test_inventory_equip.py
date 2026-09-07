import copy
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog

from subscripts.playerDataUtil import unpack_player_data_hex
from tests.fixture_saves import realistic_player_hex
from ui import inventoryTab as inv_module
from ui.inventoryTab import InventoryTab


APP = QApplication.instance() or QApplication([])


def base_item(prefab, x, y, equipped):
    return {"prefab": prefab, "stack": 1, "durability": 100.0, "grid_x": x, "grid_y": y, "equipped": equipped,
            "quality": 1, "variant": 0, "crafter_id": 0, "crafter_name": "", "custom_data": {},
            "world_level": 0, "picked_up": True}


def loaded_with(*items):
    data = unpack_player_data_hex(realistic_player_hex())
    data["inventory"] = list(items)
    return data


class FakeEditDialog:
    """Stands in for ItemEditDialog: accepts immediately with the given result."""
    result = {}

    def __init__(self, item_data, parent=None):
        self.item_data = item_data

    def exec(self):
        return QDialog.Accepted

    def get_updated_data(self):
        return dict(FakeEditDialog.result)


class InventoryEquipTests(unittest.TestCase):
    def test_equipping_dress_unequips_fenring_chest(self):
        fenring = base_item("ArmorFenringChest", 0, 0, True)
        dress = base_item("ArmorDress4", 1, 0, False)
        data = loaded_with(fenring, dress)
        before = copy.deepcopy(data)
        tab = InventoryTab()
        tab.load_data(data)

        FakeEditDialog.result = {"prefab": "ArmorDress4", "stack": 1, "durability": 100.0, "quality": 1, "variant": 0, "equipped": True}
        with patch.object(inv_module, "ItemEditDialog", FakeEditDialog):
            tab.edit_slot_item(tab.slots[(1, 0)])

        self.assertTrue(dress["equipped"])
        self.assertFalse(fenring["equipped"])
        self.assertIn("Fenris Coat", tab.equip_status.text())
        untouched = {k: v for k, v in fenring.items() if k != "equipped"}
        self.assertEqual(untouched, {k: v for k, v in before["inventory"][0].items() if k != "equipped"})
        self.assertEqual(data["skills"], before["skills"])

    def test_equipping_shield_unequips_bow(self):
        bow = base_item("Bow", 0, 0, True)
        shield = base_item("ShieldWood", 1, 0, False)
        data = loaded_with(bow, shield)
        tab = InventoryTab()
        tab.load_data(data)
        FakeEditDialog.result = {"prefab": "ShieldWood", "stack": 1, "durability": 100.0, "quality": 1, "variant": 0, "equipped": True}
        with patch.object(inv_module, "ItemEditDialog", FakeEditDialog):
            tab.edit_slot_item(tab.slots[(1, 0)])
        self.assertFalse(bow["equipped"])
        self.assertTrue(shield["equipped"])

    def test_loaded_conflicts_are_preserved_until_edited(self):
        a = base_item("ArmorFenringChest", 0, 0, True)
        b = base_item("ArmorDress4", 1, 0, True)
        data = loaded_with(a, b)
        tab = InventoryTab()
        tab.load_data(data)
        tab.save_changes()
        self.assertTrue(a["equipped"])
        self.assertTrue(b["equipped"])
        self.assertEqual(tab.equip_status.text(), "")

    def test_adding_an_equipped_item_applies_the_rule(self):
        fenring = base_item("ArmorFenringChest", 0, 0, True)
        data = loaded_with(fenring)
        tab = InventoryTab()
        tab.load_data(data)

        class FakePicker:
            selected_prefab = "ArmorDress4"

            def __init__(self, parent=None):
                pass

            def exec(self):
                return QDialog.Accepted

        FakeEditDialog.result = {"prefab": "ArmorDress4", "stack": 1, "durability": 100.0, "quality": 1, "variant": 0, "equipped": True}
        with patch.object(inv_module, "ItemPickerDialog", FakePicker), patch.object(inv_module, "ItemEditDialog", FakeEditDialog):
            tab.add_item_to_slot(tab.slots[(2, 0)])
        self.assertEqual(len(data["inventory"]), 2)
        self.assertFalse(fenring["equipped"])
        self.assertTrue(data["inventory"][1]["equipped"])


if __name__ == "__main__":
    unittest.main()
