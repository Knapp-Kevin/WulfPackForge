import unittest

from data.catalogDocument import catalog_document
from data.damage import CHEAT_DAMAGE_THRESHOLD, exceeds_cheat_threshold, total_damage


class DamageTests(unittest.TestCase):
    def test_total_damage_sums_base_and_per_level(self):
        self.assertEqual(total_damage("SwordGold_FrostFire", 1), 238.0)
        self.assertEqual(total_damage("SwordGold_FrostFire", 4), 286.0)
        self.assertIsNone(total_damage("NotARealPrefab", 1))

    def test_only_the_games_cheat_weapons_exceed_the_threshold(self):
        self.assertEqual(CHEAT_DAMAGE_THRESHOLD, 10000.0)
        self.assertTrue(exceeds_cheat_threshold("SledgeCheat", 1))
        self.assertTrue(exceeds_cheat_threshold("SwordCheat", 1))
        self.assertFalse(exceeds_cheat_threshold("SwordGold_FrostFire", 4))
        self.assertFalse(exceeds_cheat_threshold("NotARealPrefab", 1))
        over = [r["prefab"] for r in catalog_document()["items"] if exceeds_cheat_threshold(r["prefab"], 1)]
        self.assertEqual(sorted(over), ["SledgeCheat", "SwordCheat"])


if __name__ == "__main__":
    unittest.main()
