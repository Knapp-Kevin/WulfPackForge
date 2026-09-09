"""The inventory add and remove paths must tolerate the payload shapes ``load_data`` tolerates.

``load_data`` reads the inventory with ``.get("inventory", [])`` while the add and remove paths
indexed it strictly. The parser always sets the key today, so this was an unstated assumption
rather than a live defect; these tests make the disagreement impossible to reintroduce.
"""
import os
import unittest
import unittest.mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog

import ui.inventoryTab as it
from subscripts.playerDataUtil import new_inventory_item, pack_player_data_hex, unpack_player_data_hex
from tests.fixture_saves import realistic_player_data
from tests.qt_support import QtTestCase
from ui.inventoryTab import InventoryTab

APP = QApplication.instance() or QApplication([])
PREFAB = "StaffRedTroll"


class FakePicker:
    def __init__(self, parent=None):
        self.selected_prefab = PREFAB

    def exec(self):
        return QDialog.Accepted


class FakeEditor:
    def __init__(self, item_data, parent=None):
        self.item_data = item_data

    def exec(self):
        return QDialog.Accepted

    def get_updated_data(self):
        return {"prefab": PREFAB, "stack": 1, "durability": 200.0,
                "quality": 1, "variant": 0, "equipped": False}


class InventoryPayloadShapeTests(QtTestCase):
    def setUp(self):
        self.tab = InventoryTab()
        self._patches = [
            unittest.mock.patch.object(it, "ItemPickerDialog", FakePicker),
            unittest.mock.patch.object(it, "ItemEditDialog", FakeEditor),
        ]
        for started in self._patches:
            started.start()

    def tearDown(self):
        for started in self._patches:
            started.stop()
        super().tearDown()

    @staticmethod
    def _payload_without_inventory():
        """A real payload with the key removed. An empty dict is falsy, and every guard in the
        tab reads it as "no character loaded", so it would not exercise the paths at all."""
        payload = realistic_player_data()
        payload.pop("inventory")
        return payload

    def test_adding_an_item_to_a_payload_without_an_inventory_key_succeeds(self):
        payload = self._payload_without_inventory()
        self.tab.load_data(payload)
        self.tab.add_item_to_slot(self.tab.slots[(0, 0)])
        self.assertEqual([item["prefab"] for item in payload["inventory"]], [PREFAB])
        self.assertEqual(self.tab.slots[(0, 0)].item_data["prefab"], PREFAB)

    def test_removing_an_item_from_a_payload_without_an_inventory_key_does_not_raise(self):
        payload = self._payload_without_inventory()
        self.tab.load_data(payload)
        slot = self.tab.slots[(1, 0)]
        slot.set_item({"prefab": PREFAB, "stack": 1, "grid_x": 1, "grid_y": 0, "quality": 1, "variant": 0})
        self.tab.delete_slot_item(slot, confirm=False)
        self.assertIsNone(slot.item_data)
        self.assertEqual(payload["inventory"], [])


class NewInventoryItemTests(unittest.TestCase):
    def test_a_new_inventory_item_carries_every_field_the_codec_writes(self):
        payload = realistic_player_data()
        fresh = new_inventory_item(PREFAB, 3, 2, 200.0)
        payload["inventory"] = [fresh]
        restored = unpack_player_data_hex(pack_player_data_hex(payload))["inventory"][0]
        self.assertEqual(set(restored), set(fresh), "the helper and the codec disagree on the record shape")
        durability = restored.pop("durability")
        expected = fresh.copy()
        self.assertAlmostEqual(durability, expected.pop("durability"), places=3)  # stored as float32
        self.assertEqual(restored, expected)


if __name__ == "__main__":
    unittest.main()
