"""The prefab-hash index follows the mod registry: registered items resolve, cleared ones do not, never stale."""
import unittest

from data.itemHashes import hash_index
from data.items import ItemDefinition, clear_registered_items, register_items
from subscripts.stableHash import stable_hash_code


def index():
    return hash_index(stable_hash_code)


class HashIndexRegistryTests(unittest.TestCase):
    def tearDown(self):
        clear_registered_items()

    def test_a_registered_mod_item_becomes_resolvable(self):
        self.assertNotIn(stable_hash_code("ZzModdedBlade"), index())
        register_items([ItemDefinition(prefab="ZzModdedBlade", display_name="Modded Blade")])
        self.assertEqual(index()[stable_hash_code("ZzModdedBlade")], "ZzModdedBlade")

    def test_clearing_registered_items_removes_them_from_the_index(self):
        register_items([ItemDefinition(prefab="ZzModdedBlade", display_name="Modded Blade")])
        clear_registered_items()
        self.assertNotIn(stable_hash_code("ZzModdedBlade"), index())

    def test_register_clear_register_does_not_serve_a_stale_index(self):
        register_items([ItemDefinition(prefab="ZzModdedA", display_name="A")])
        clear_registered_items()
        register_items([ItemDefinition(prefab="ZzModdedB", display_name="B")])
        resolved = index()
        self.assertEqual(resolved.get(stable_hash_code("ZzModdedB")), "ZzModdedB")
        self.assertNotIn(stable_hash_code("ZzModdedA"), resolved)


if __name__ == "__main__":
    unittest.main()
