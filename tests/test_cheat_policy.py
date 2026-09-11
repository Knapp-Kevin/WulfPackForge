"""The cheat-flag policy (META_LEDGER #175): preserve verbatim, never set, surface the risk."""
import copy
import unittest

from subscripts.cheatRisk import CheatRisk, from_character, risk_lines
from subscripts.playerDataUtil import new_inventory_item, pack_player_data_hex, unpack_player_data_hex
from tests.fixture_saves import realistic_root_save, realistic_v33_player_data


def clean_v33_payload() -> dict:
    """The v33 fixture with its one cheated item cleared, so 'clean' is a stated precondition."""
    data = realistic_v33_player_data()
    for item in data["inventory"]:
        item["_wire"]["cheat_flags"] = 0
    return data


class CheatPolicyTests(unittest.TestCase):
    def test_a_cheated_item_stays_cheated_through_the_round_trip(self):
        data = realistic_v33_player_data()
        restored = unpack_player_data_hex(pack_player_data_hex(data))
        self.assertEqual([item["_wire"]["cheat_flags"] for item in restored["inventory"]], [1, 0, 0])

    def test_round_tripping_a_clean_payload_sets_no_cheat_flag(self):
        root, data = realistic_root_save(), clean_v33_payload()
        restored = unpack_player_data_hex(pack_player_data_hex(data))
        self.assertTrue(all(item["_wire"]["cheat_flags"] == 0 for item in restored["inventory"]))
        self.assertEqual(root["used_cheats"], realistic_root_save()["used_cheats"])

    def test_a_new_item_is_written_clean(self):
        data = clean_v33_payload()
        data["inventory"] = [new_inventory_item("Torch", 0, 0, 20.0)]
        restored = unpack_player_data_hex(pack_player_data_hex(data))
        self.assertEqual(restored["inventory"][0]["_wire"]["cheat_flags"], 0)

    def test_from_character_counts_cheated_items_from_the_payload(self):
        self.assertEqual(from_character(realistic_root_save(), realistic_v33_player_data()).cheated_items, 1)
        legacy = {"inventory": [new_inventory_item("Wood", 0, 0, 100.0)]}
        self.assertEqual(from_character({}, legacy).cheated_items, 0)
        other_bit = clean_v33_payload()
        other_bit["inventory"][0]["_wire"]["cheat_flags"] = 2
        self.assertEqual(from_character({}, other_bit).cheated_items, 0)

    def test_the_bypass_key_is_detected_case_insensitively_and_never_written(self):
        data = clean_v33_payload()
        data["uniques"] = ["invrows 4", "BypassCheatChecks 1"]
        before = copy.deepcopy(data["uniques"])
        self.assertTrue(from_character({}, data).bypass_active)
        self.assertEqual(data["uniques"], before)
        self.assertEqual(unpack_player_data_hex(pack_player_data_hex(data))["uniques"], before)
        self.assertFalse(from_character({}, {"uniques": ["bypasscheatchecks 0"]}).bypass_active)
        self.assertFalse(from_character({}, {"uniques": []}).bypass_active)

    def test_risk_lines_never_claim_the_character_is_safe(self):
        lines = risk_lines(CheatRisk(profile_flag=False, cheated_items=0, bypass_active=False))
        self.assertEqual(len(lines), 4)
        self.assertIn("world cheat state", lines[-1])
        self.assertFalse(any("safe" in line.lower() for line in lines))
        self.assertIn("2", risk_lines(CheatRisk(profile_flag=True, cheated_items=2, bypass_active=True))[1])


if __name__ == "__main__":
    unittest.main()
