import copy
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from subscripts.playerDataUtil import unpack_player_data_hex
from tests.fixture_saves import realistic_player_hex
from ui.appearanceTab import AppearanceTab
from ui.miscTab import MiscTab
from ui.skillsTab import SkillsTab
from ui.statsTab import StatsTab


APP = QApplication.instance() or QApplication([])


def loaded_player_data() -> dict:
    """Player data exactly as the main window would hold it (float32-rounded)."""
    return unpack_player_data_hex(realistic_player_hex())


class SkillsTabPreserveTests(unittest.TestCase):
    def test_skills_noop_preserves_unknown_id_and_precision(self):
        data = loaded_player_data()
        baseline = copy.deepcopy(data)
        tab = SkillsTab()
        tab.load_data(data)
        tab.save_changes()
        self.assertEqual(data, baseline)
        self.assertEqual([s["id"] for s in data["skills"]], [1, 500])

    def test_editing_one_level_changes_only_that_skill(self):
        data = loaded_player_data()
        baseline = copy.deepcopy(data)
        tab = SkillsTab()
        tab.load_data(data)
        tab.table.cellWidget(1, 1).setValue(77.0)
        tab.save_changes()
        self.assertEqual(data["skills"][1], {"id": 500, "level": 77.0, "xp": baseline["skills"][1]["xp"]})
        self.assertEqual(data["skills"][0], baseline["skills"][0])

    def test_reloading_a_smaller_character_saves_cleanly(self):
        first = loaded_player_data()
        second = loaded_player_data()
        second["skills"] = second["skills"][:1]
        baseline = copy.deepcopy(second)
        tab = SkillsTab()
        tab.load_data(first)
        tab.load_data(second)
        tab.save_changes()
        self.assertEqual(second, baseline)


class AppearanceTabPreserveTests(unittest.TestCase):
    def test_noop_preserves_unknown_hair_and_model(self):
        data = loaded_player_data()
        baseline = copy.deepcopy(data)
        tab = AppearanceTab()
        tab.load_data(data)
        self.assertEqual(tab.hair_combo.currentText(), "Unknown (HairModded99)")
        self.assertEqual(tab.model_combo.currentData(), 2)
        tab.save_changes()
        self.assertEqual(data, baseline)

    def test_unknown_entries_are_removed_when_a_vanilla_character_loads(self):
        modded = loaded_player_data()
        vanilla = loaded_player_data()
        vanilla["hair"] = "Hair1"
        vanilla["model_index"] = 0
        tab = AppearanceTab()
        tab.load_data(modded)
        tab.load_data(vanilla)
        labels = [tab.hair_combo.itemText(i) for i in range(tab.hair_combo.count())]
        self.assertNotIn("Unknown (HairModded99)", labels)
        self.assertEqual(tab.hair_combo.currentData(), "Hair1")

    def test_picking_a_colour_writes_only_skin_color(self):
        data = loaded_player_data()
        baseline = copy.deepcopy(data)
        tab = AppearanceTab()
        tab.load_data(data)
        with patch("ui.appearanceTab.QColorDialog.getColor", return_value=QColor(255, 0, 0)):
            tab.choose_skin_color()
        tab.save_changes()
        self.assertEqual(data["skin_color"], [1.0, 0.0, 0.0])
        for key in baseline:
            if key != "skin_color":
                self.assertEqual(data[key], baseline[key], key)

    def test_hdr_controls_are_opt_in_and_negative_values_are_prohibited(self):
        tab = AppearanceTab()
        data = loaded_player_data()
        tab.load_data(data)

        self.assertFalse(tab.overbright_checkbox.isChecked())
        self.assertFalse(tab.skin_hdr_spins[0].isEnabled())

        tab.overbright_checkbox.setChecked(True)
        self.assertTrue(tab.skin_hdr_spins[0].isEnabled())
        tab.skin_hdr_spins[0].setValue(-5.0)
        self.assertEqual(tab.skin_hdr_spins[0].value(), 0.0)
        self.assertEqual(tab.current_skin_rgb[0], 0.0)

    def test_overbright_values_save_without_clamping(self):
        tab = AppearanceTab()
        data = loaded_player_data()
        baseline = copy.deepcopy(data)
        tab.load_data(data)
        tab.overbright_checkbox.setChecked(True)
        for spin, value in zip(tab.skin_hdr_spins, (2.0, 3.0, 4.0)):
            spin.setValue(value)
        for spin, value in zip(tab.hair_hdr_spins, (0.5, 2.5, 4.0)):
            spin.setValue(value)

        tab.save_changes()
        self.assertEqual(data["skin_color"], [2.0, 3.0, 4.0])
        self.assertEqual(data["hair_color"], [0.5, 2.5, 4.0])
        for key in baseline:
            if key not in ("skin_color", "hair_color"):
                self.assertEqual(data[key], baseline[key], key)

    def test_existing_overbright_character_loads_enabled_and_round_trips(self):
        data = loaded_player_data()
        data["skin_color"] = [2.0, 2.0, 2.0]
        data["hair_color"] = [1.0, 2.0, 4.0]
        baseline = copy.deepcopy(data)

        tab = AppearanceTab()
        tab.load_data(data)
        self.assertTrue(tab.overbright_checkbox.isChecked())
        self.assertEqual([spin.value() for spin in tab.skin_hdr_spins], [2.0, 2.0, 2.0])
        self.assertEqual([spin.value() for spin in tab.hair_hdr_spins], [1.0, 2.0, 4.0])
        tab.save_changes()
        self.assertEqual(data, baseline)

    def test_glow_preset_preserves_hue_and_sets_peak_intensity(self):
        data = loaded_player_data()
        data["skin_color"] = [0.25, 0.5, 1.0]
        tab = AppearanceTab()
        tab.load_data(data)
        tab.overbright_checkbox.setChecked(True)
        tab.preset_target_combo.setCurrentIndex(tab.preset_target_combo.findData("skin"))
        tab.apply_intensity_preset(4.0)

        self.assertEqual(tab.current_skin_rgb, [1.0, 2.0, 4.0])
        self.assertEqual(tab.skin_intensity_label.text(), "HDR 4.00×")

    def test_extreme_values_show_warning(self):
        data = loaded_player_data()
        tab = AppearanceTab()
        tab.load_data(data)
        tab.overbright_checkbox.setChecked(True)
        tab.skin_hdr_spins[0].setValue(8.0)
        self.assertIn("Extreme overbright", tab.hdr_warning_label.text())


class StatsTabPreserveTests(unittest.TestCase):
    def test_noop_preserves_four_foods_low_vitals_and_food_precision(self):
        data = loaded_player_data()
        baseline = copy.deepcopy(data)
        tab = StatsTab()
        root = {"used_cheats": False}
        tab.load_data(data, root)
        self.assertEqual(tab.food_table.rowCount(), 4)
        tab.save_changes()
        self.assertEqual(data, baseline)
        self.assertEqual(data["max_health"], 10.0)
        self.assertEqual(root, {"used_cheats": False})

    def test_editing_max_health_changes_only_that_field(self):
        data = loaded_player_data()
        baseline = copy.deepcopy(data)
        tab = StatsTab()
        tab.load_data(data, {"used_cheats": False})
        tab.max_health_spin.setValue(150.0)
        tab.save_changes()
        self.assertEqual(data["max_health"], 150.0)
        for key in baseline:
            if key != "max_health":
                self.assertEqual(data[key], baseline[key], key)


class MiscTabPreserveTests(unittest.TestCase):
    def test_rename_writes_only_root_name(self):
        data = loaded_player_data()
        baseline = copy.deepcopy(data)
        root = {"character_name": "Frostwülf"}
        tab = MiscTab()
        tab.load_data(data, root)
        tab.save_changes()
        self.assertEqual(root, {"character_name": "Frostwülf"})
        tab.name_input.setText("Renamed")
        tab.save_changes()
        self.assertEqual(root["character_name"], "Renamed")
        self.assertEqual(data, baseline)
        self.assertNotIn("character_name", data)


if __name__ == "__main__":
    unittest.main()
