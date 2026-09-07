import copy
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from data.skills import VALHEIM_SKILLS
from subscripts.playerDataUtil import unpack_player_data_hex
from tests.fixture_saves import realistic_player_hex
from ui.skillsTab import SkillsTab


APP = QApplication.instance() or QApplication([])
VANILLA_IDS = sorted(skill_id for skill_id in VALHEIM_SKILLS if skill_id)


class SkillsAddAllTests(unittest.TestCase):
    def test_empty_character_shows_hint_and_add_all_seeds_every_vanilla_skill(self):
        data = unpack_player_data_hex(realistic_player_hex())
        data["skills"] = []
        tab = SkillsTab()
        tab.load_data(data)
        self.assertEqual(tab.table.rowCount(), 0)
        self.assertTrue(tab.empty_hint.isVisibleTo(tab))
        self.assertTrue(tab.btn_add_all_skills.isEnabled())
        self.assertEqual(tab.add_skill_combo.count(), len(VANILLA_IDS))

        tab.add_all_skills()
        self.assertEqual(sorted(skill["id"] for skill in data["skills"]), VANILLA_IDS)
        self.assertTrue(all(skill["level"] == 0.0 and skill["xp"] == 0.0 for skill in data["skills"]))
        self.assertEqual(tab.table.rowCount(), len(VANILLA_IDS))
        self.assertFalse(tab.empty_hint.isVisibleTo(tab))
        self.assertFalse(tab.btn_add_all_skills.isEnabled())
        self.assertEqual(tab.add_skill_combo.count(), 0)

    def test_add_all_only_fills_the_gaps_and_edits_survive_save(self):
        data = unpack_player_data_hex(realistic_player_hex())
        before = copy.deepcopy(data["skills"])
        tab = SkillsTab()
        tab.load_data(data)
        self.assertFalse(tab.empty_hint.isVisibleTo(tab))
        tab.add_all_skills()
        self.assertEqual(data["skills"][: len(before)], before)
        self.assertEqual(len({skill["id"] for skill in data["skills"]}), len(data["skills"]))
        last_row = tab.table.rowCount() - 1
        tab.table.cellWidget(last_row, 1).setValue(42.0)
        tab.save_changes()
        self.assertEqual(data["skills"][-1]["level"], 42.0)


if __name__ == "__main__":
    unittest.main()
