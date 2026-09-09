"""Rebuilding the inventory slot grid must release the previous widgets cleanly.

The teardown that this covers caused a native access violation: it obtained each widget through
``layout.itemAt(i)`` and reparented it, which makes Qt delete the layout item while a wrapper for
it is still live. The crash surfaced much later, in an unrelated dialog, when Qt reused the
address. These tests assert the observable half - the grid is genuinely rebuilt and nothing is
left behind - while ``tests/test_razor.py`` forbids the pattern itself.
"""
import gc
import os
import unittest
import weakref

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shiboken6
from PySide6.QtWidgets import QApplication, QWidget, QWidgetItem

from tests.qt_support import QtTestCase
from ui.inventoryTab import InventoryTab

APP = QApplication.instance() or QApplication([])
CELLS = InventoryTab.GRID_WIDTH * InventoryTab.GRID_HEIGHT


def _payload(prefabs):
    return {"inventory": [{"prefab": prefab, "stack": 1, "durability": 100.0, "grid_x": x, "grid_y": 0,
                           "equipped": False, "quality": 1, "variant": 0, "crafter_id": 0,
                           "crafter_name": "", "custom_data": {}, "world_level": 0, "picked_up": True}
                          for x, prefab in enumerate(prefabs)]}


class GridTeardownTests(QtTestCase):
    def setUp(self):
        self.tab = InventoryTab()

    def test_rebuilding_the_grid_destroys_the_previous_slots(self):
        doomed = [weakref.ref(slot) for slot in self.tab.slots.values()]
        self.assertEqual(len(doomed), CELLS)
        self.tab.init_empty_grid()
        gc.collect()
        alive = [ref for ref in doomed if ref() is not None]
        self.assertEqual(alive, [], f"{len(alive)} slot widgets survived the rebuild")
        self.assertEqual(len(self.tab.slots), CELLS)

    def test_rebuilding_the_grid_leaves_no_layout_items_behind(self):
        self.tab.init_empty_grid()
        self.assertEqual(self.tab.grid_layout.count(), CELLS)
        placed = {self.tab.grid_layout.itemAt(i).widget() for i in range(self.tab.grid_layout.count())}
        self.assertEqual(placed, set(self.tab.slots.values()),
                         "the layout holds widgets that are not the current slots")

    def test_repeated_rebuilds_do_not_accumulate_items(self):
        for _ in range(5):
            self.tab.init_empty_grid()
        self.assertEqual(self.tab.grid_layout.count(), CELLS)
        self.assertEqual(len(self.tab.slots), CELLS)

    def test_a_layout_item_the_grid_did_not_add_is_still_drained(self):
        """The one deterministic guard for the defect itself.

        The previous teardown reparented each widget and let the layout dispose of its own item.
        An item put into the layout directly is not cleaned up that way and survives the rebuild,
        so the layout ends up with thirty-three entries instead of thirty-two. `takeAt` drains
        whatever is there. Measured across five runs of each build: 33 before, 32 after, every
        time - so this fails on the defective teardown without waiting for a crash.
        """
        holder = QWidget()
        probe = QWidgetItem(holder)
        self.tab.grid_layout.addItem(probe, InventoryTab.GRID_HEIGHT, 0)
        self.assertEqual(self.tab.grid_layout.count(), CELLS + 1)
        self.tab.init_empty_grid()
        self.assertEqual(self.tab.grid_layout.count(), CELLS,
                         "the teardown left an item it did not add behind")
        self.assertTrue(shiboken6.isValid(probe),
                        "nothing should have deleted the probe out from under this reference")

    def test_loading_a_character_twice_keeps_one_slot_per_cell(self):
        payload = _payload(["StaffRedTroll", "SwordBronze"])
        self.tab.load_data(payload)
        self.tab.load_data(payload)
        self.assertEqual(self.tab.grid_layout.count(), CELLS)
        self.assertEqual(self.tab.slots[(0, 0)].item_data["prefab"], "StaffRedTroll")
        self.assertEqual(self.tab.slots[(1, 0)].item_data["prefab"], "SwordBronze")
        self.assertIsNone(self.tab.slots[(2, 0)].item_data)


if __name__ == "__main__":
    unittest.main()
