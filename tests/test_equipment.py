import copy
import unittest

from data.equipment import conflicts, hands_for, resolve_equip, role_for, slot_for
from data.items import resolve_item


def item(prefab, equipped=True, **extra):
    base = {"prefab": prefab, "stack": 1, "durability": 100.0, "grid_x": 0, "grid_y": 0, "equipped": equipped,
            "quality": 1, "variant": 0, "crafter_id": 0, "crafter_name": "", "custom_data": {},
            "world_level": 0, "picked_up": True}
    base.update(extra)
    return base


class RoleAndSlotTests(unittest.TestCase):
    def test_roles(self):
        self.assertEqual(role_for(resolve_item("ArmorDress4")), "clothing")
        self.assertEqual(role_for(resolve_item("ArmorFenringChest")), "armor")
        self.assertEqual(role_for(resolve_item("GoblinArmband")), "creature")
        self.assertEqual(role_for(resolve_item("HelmetDverger")), "armor")
        self.assertEqual(role_for(resolve_item("CapeOdin")), "clothing")
        self.assertEqual(role_for(resolve_item("SwordBronze")), "weapon")
        self.assertEqual(role_for(resolve_item("BeltStrength")), "accessory")
        self.assertEqual(role_for(resolve_item("Wood")), "none")
        self.assertEqual(role_for(None), "none")

    def test_creature_attacks_are_not_player_items(self):
        for prefab in ("troll_log_swing_h", "draugr_bow", "skeleton_bow", "charred_greatsword_swing",
                       "SeekerBrute_Taunt", "PlayerUnarmed", "charred_magestaff_fire", "draugr_arrow"):
            self.assertEqual(role_for(resolve_item(prefab)), "creature", prefab)
        self.assertEqual(role_for(resolve_item("SwordCheat")), "internal")
        self.assertEqual(role_for(resolve_item("ShieldKnight")), "internal")
        for prefab in ("FistBjornClaw", "BombOoze", "Tankard_dvergr", "FishingRod"):
            self.assertEqual(role_for(resolve_item(prefab)), "weapon", prefab)
        self.assertEqual(role_for(resolve_item("chest_hildir1")), "none")

    def test_slots_and_hands(self):
        self.assertEqual(slot_for(resolve_item("ArmorDress4")), "chest")
        self.assertEqual(slot_for(resolve_item("ArmorFenringChest")), "chest")
        self.assertEqual(slot_for(resolve_item("ArmorFenringLegs")), "legs")
        self.assertEqual(slot_for(resolve_item("BeltStrength")), "utility")
        self.assertIsNone(slot_for(resolve_item("Wood")))
        self.assertEqual(hands_for(resolve_item("SwordBronze")), "right")
        self.assertEqual(hands_for(resolve_item("Bow")), "both")
        self.assertEqual(hands_for(resolve_item("ShieldWood")), "left")
        self.assertIsNone(hands_for(resolve_item("Wood")))


class ConflictTests(unittest.TestCase):
    def test_slot_and_hand_conflicts(self):
        self.assertTrue(conflicts("ArmorDress4", "ArmorFenringChest"))
        self.assertFalse(conflicts("ArmorDress4", "ArmorFenringLegs"))
        self.assertTrue(conflicts("Bow", "ShieldWood"))
        self.assertTrue(conflicts("ShieldWood", "Bow"))
        self.assertFalse(conflicts("SwordBronze", "ShieldWood"))
        self.assertTrue(conflicts("SwordBronze", "SwordIron"))
        self.assertFalse(conflicts("MyModdedHammer", "ArmorFenringChest"))
        self.assertFalse(conflicts("Wood", "Wood"))

    def test_resolve_equip_unequips_only_conflicting_chest(self):
        fenring = item("ArmorFenringChest", grid_x=1)
        legs = item("ArmorFenringLegs", grid_x=2)
        dress = item("ArmorDress4", grid_x=3)
        wood = item("Wood", equipped=False, grid_x=4, stack=50)
        inventory = [fenring, legs, dress, wood]
        before = copy.deepcopy(inventory)

        changed = resolve_equip(inventory, dress)

        self.assertEqual(changed, [fenring])
        self.assertFalse(fenring["equipped"])
        self.assertTrue(dress["equipped"])
        self.assertEqual(legs, before[1])
        self.assertEqual(wood, before[3])
        self.assertEqual({k: v for k, v in fenring.items() if k != "equipped"},
                         {k: v for k, v in before[0].items() if k != "equipped"})

    def test_resolve_equip_with_two_handed_clears_shield_and_weapon(self):
        sword = item("SwordBronze", grid_x=1)
        shield = item("ShieldWood", grid_x=2)
        bow = item("Bow", grid_x=3)
        inventory = [sword, shield, bow]
        changed = resolve_equip(inventory, bow)
        self.assertEqual({c["prefab"] for c in changed}, {"SwordBronze", "ShieldWood"})

    def test_resolve_equip_is_noop_for_unequipped_or_unknown(self):
        fenring = item("ArmorFenringChest")
        modded = item("MyModdedHammer")
        inventory = [fenring, modded]
        self.assertEqual(resolve_equip(inventory, modded), [])
        self.assertTrue(fenring["equipped"])
        dress = item("ArmorDress4", equipped=False)
        inventory.append(dress)
        self.assertEqual(resolve_equip(inventory, dress), [])


if __name__ == "__main__":
    unittest.main()
