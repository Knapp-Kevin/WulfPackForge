import unittest

from data.item_groups import GROUPS, EXCLUDED_TYPES, group_for, items_in_group, items_under, navigation_tree, tier_rank
from data.items import ITEMS, resolve_item


class ItemGroupTests(unittest.TestCase):
    def test_groups_are_in_the_curated_order(self):
        self.assertEqual(
            GROUPS,
            ("Weapons", "Bows and Ammo", "Shields", "Helmets", "Chest Armor", "Leg Armor", "Capes",
             "Clothing and Hats", "Accessories", "Tools", "Materials", "Food and Mead", "Trophies",
             "Misc"),
        )

    def test_creature_attacks_leave_the_weapon_lists(self):
        weapons = [i.prefab for i in items_in_group("Weapons")]
        bows = [i.prefab for i in items_in_group("Bows and Ammo")]
        for prefab in ("troll_log_swing_h", "draugr_axe", "SeekerBrute_Taunt", "PlayerUnarmed", "SwordCheat"):
            self.assertNotIn(prefab, weapons, prefab)
        self.assertNotIn("skeleton_bow", bows)
        from data.item_groups import pickable_items
        pickable = {i.prefab for i in pickable_items()}
        for prefab in ("troll_log_swing_h", "skeleton_bow", "GoblinArmband", "SwordCheat", "PlayerUnarmed"):
            self.assertNotIn(prefab, pickable, prefab)
            self.assertIsNone(group_for(resolve_item(prefab)), prefab)
        weapon_tree = dict(dict(navigation_tree())["Weapons"])
        self.assertIn("Bombs", weapon_tree)
        self.assertIn("Pickaxes", weapon_tree)

    def test_every_selectable_item_has_one_group(self):
        from data.equipment import role_for
        for item in ITEMS:
            group = group_for(item)
            if item.item_type in EXCLUDED_TYPES or role_for(item) in ("creature", "internal"):
                self.assertIsNone(group, item.prefab)
            else:
                self.assertIn(group, GROUPS, item.prefab)
        grouped = sum(len(items_in_group(name)) for name in GROUPS)
        pickable = sum(1 for item in ITEMS if group_for(item) is not None)
        self.assertEqual(grouped, pickable)

    def test_customization_rows_are_excluded(self):
        customization = next(item for item in ITEMS if item.item_type == "Customization")
        self.assertIsNone(group_for(customization))
        self.assertFalse(any(i.prefab == customization.prefab for i in items_in_group("Misc")))

    def test_weapons_sorted_by_material_tier(self):
        weapons = [item.prefab for item in items_in_group("Weapons")]
        self.assertIn("SwordBronze", weapons)
        self.assertLess(weapons.index("SwordBronze"), weapons.index("SwordIron"))
        self.assertLess(weapons.index("SwordIron"), weapons.index("SwordBlackmetal"))
        self.assertLess(tier_rank("AxeBronze"), tier_rank("AxeIron"))
        self.assertLess(tier_rank("AxeIron"), tier_rank("AxeBlackMetal"))

    def test_group_membership_examples(self):
        self.assertEqual(group_for(resolve_item("ArrowIron")), "Bows and Ammo")
        self.assertEqual(group_for(resolve_item("HelmetBronze")), "Helmets")
        self.assertEqual(group_for(resolve_item("ArmorFenringChest")), "Chest Armor")
        self.assertEqual(group_for(resolve_item("ArmorDress4")), "Clothing and Hats")
        self.assertEqual(group_for(resolve_item("HelmetHat1")), "Clothing and Hats")
        self.assertEqual(group_for(resolve_item("CapeWolf")), "Capes")
        self.assertIsNone(group_for(resolve_item("GoblinArmband")))
        self.assertEqual(group_for(resolve_item("BeltStrength")), "Accessories")
        self.assertEqual(group_for(resolve_item("Wood")), "Materials")
        self.assertEqual(group_for(resolve_item("TrophyBoar")), "Trophies")

    def test_named_weapons_sit_in_their_crafting_tier_and_nothing_hides_below_a_type(self):
        from data.item_groups import OTHER_MATERIAL, material_for, navigation_tree
        self.assertEqual(material_for(resolve_item("SpearSplitner")), "Flametal")
        flametal_spears = {i.prefab for i in items_under("Weapons", "Spears", "Flametal")}
        for prefab in ("SpearSplitner", "SpearSplitner_Blood", "SpearSplitner_Lightning", "SpearSplitner_Nature"):
            self.assertIn(prefab, flametal_spears)
        self.assertEqual(material_for(resolve_item("SwordMistwalker")), "Eitr")
        self.assertEqual(material_for(resolve_item("THSwordSlayerBlood")), "Flametal")
        self.assertIsNone(material_for(resolve_item("BombBile")))
        for group, branches in navigation_tree():
            for subgroup, materials in branches:
                if not materials:
                    continue
                reachable = set()
                for material in materials:
                    reachable |= {i.prefab for i in items_under(group, subgroup, material)}
                self.assertEqual(reachable, {i.prefab for i in items_under(group, subgroup)}, (group, subgroup))
                if OTHER_MATERIAL in materials:
                    self.assertEqual(materials[-1], OTHER_MATERIAL)

    def test_navigation_tree_branches_weapons_by_type_then_material(self):
        tree = dict(navigation_tree())
        self.assertEqual(list(tree), list(GROUPS))
        weapons = dict(tree["Weapons"])
        self.assertIn("Swords", weapons)
        self.assertIn("Bronze", weapons["Swords"])
        self.assertEqual([i.prefab for i in items_under("Weapons", "Swords", "Bronze")], ["SwordBronze"])
        swords = [i.prefab for i in items_under("Weapons", "Swords")]
        self.assertLess(swords.index("SwordBronze"), swords.index("SwordIron"))
        self.assertEqual(items_under("Weapons"), items_in_group("Weapons"))
        self.assertEqual(tree["Materials"], [])


if __name__ == "__main__":
    unittest.main()
