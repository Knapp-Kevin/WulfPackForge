"""The vanilla-friendly appearance mode, end to end through the main window (phase 46)."""
import os
import shutil
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialogButtonBox, QPushButton

from data.skinPalette import palette_tints
from subscripts.editorMode import MODE_FULL, MODE_VANILLA, load_mode
from subscripts.newCharacter import DEFAULT_SKIN
from subscripts.saveSafety import verify_fch_round_trip
from subscripts.valheim_detection import ScanState, ValheimScan
from tests.fixture_saves import realistic_root_save, write_fch
from tests.qt_support import dispose
from tools.compare_saves import compare
from ui import editorModeBar, mainWindow as mw, newCharacterDialog as ncd
from ui.editorModeBar import HAIR_CAP_REQUIRED, PALETTE_REQUIRED
from ui.hdrColorControls import MAX_HDR_COMPONENT
from ui.newCharacterDialog import NewCharacterDialog
from ui.skinPaletteDialog import SkinPaletteDialog

APP = QApplication.instance() or QApplication([])
TONES = palette_tints()


def _fields(differences):
    """The distinct fields a comparison names, sorted; a list field yields one line per element."""
    return sorted({line.split(":")[0] for line in differences})


class RecordingMessageBox:
    calls = []
    Warning = 0
    Ok = 0

    def __init__(self, *args, **kwargs):
        RecordingMessageBox.calls.append(("startup", "constructed"))

    def setWindowTitle(self, *a): pass
    def setText(self, *a): pass
    def setInformativeText(self, *a): pass
    def setIcon(self, *a): pass
    def setStandardButtons(self, *a): pass
    def exec(self): return 0

    @classmethod
    def information(cls, *args, **kwargs): cls.calls.append(("info", args[1]))

    @classmethod
    def warning(cls, *args, **kwargs): cls.calls.append(("warn", args[1], args[2]))

    @classmethod
    def critical(cls, *args, **kwargs): cls.calls.append(("crit", args[1], args[2]))


class VanillaModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.save_dir = root / "characters_local"
        self.save_dir.mkdir()
        self.source = write_fch(self.save_dir / "hero.fch", realistic_root_save())
        self.before = root / "before.fch"
        shutil.copy(self.source, self.before)
        self.workspace_root = root / "workspace"
        RecordingMessageBox.calls = []
        self.stack = ExitStack()
        self.stack.enter_context(patch("subscripts.workspace.default_workspace_root", return_value=self.workspace_root))
        self.stack.enter_context(patch.object(mw, "scan_valheim", side_effect=lambda: ValheimScan(state=ScanState.NOT_RUNNING)))
        self.stack.enter_context(patch.object(mw, "discover_character_records", return_value=[]))
        self.stack.enter_context(patch.object(mw, "QMessageBox", RecordingMessageBox))
        self.window = mw.MainWindow(startup_warning=False)
        self.window.load_save_file(str(self.source))

    def tearDown(self):
        dispose(self.window)
        self.window = None
        self.stack.close()
        self.temp.cleanup()

    def _mode(self, on: bool):
        self.window.mode_bar.switch.setChecked(on)

    def _pick(self, tone_index: int):
        with patch.object(SkinPaletteDialog, "pick", return_value=list(TONES[tone_index - 1])):
            self.window.appearance_tab.choose_skin_color()

    def test_read_only_tabs_write_nothing(self):
        self._mode(True)
        self._pick(4)
        inventory_before = [dict(item) for item in self.window.player_data["inventory"]]
        with patch.object(mw.InventoryTab, "edit_slot_item") as editor, patch.object(mw.InventoryTab, "add_item_to_slot") as adder:
            slot = self.window.inventory_tab.slots[(0, 0)]
            self.assertFalse(slot.isEnabledTo(self.window.inventory_tab))
            slot.click()
        editor.assert_not_called()
        adder.assert_not_called()
        self.assertEqual(self.window.player_data["inventory"], inventory_before)
        skills = self.window.skills_tab
        self.assertFalse(skills.table.isEnabledTo(skills))
        for button in (skills.btn_max_all, skills.btn_set_all0, skills.btn_add_skill, skills.btn_add_all_skills):
            self.assertFalse(button.isEnabledTo(skills))
        self.window.save_save_file()
        self.assertEqual(_fields(compare(str(self.before), str(self.source))), ["payload.skin_color"])

    def test_palette_pick_writes_only_the_skin_tint(self):
        self._mode(True)
        self._pick(4)
        self.assertEqual(self.window.appearance_tab.current_skin_rgb, list(TONES[3]))
        self.assertIsNone(self.window.mode_bar.blocking_reason(self.window))
        self.window.save_save_file()
        self.assertEqual(_fields(compare(str(self.before), str(self.source))), ["payload.skin_color"])
        verify_fch_round_trip(str(self.source))

    def test_an_off_palette_skin_blocks_the_save_until_a_tone_is_chosen(self):
        self._mode(True)
        original = self.source.read_bytes()
        self.assertEqual(self.window.mode_bar.blocking_reason(self.window), PALETTE_REQUIRED)
        self.window.save_save_file()
        self.assertEqual(RecordingMessageBox.calls[-1][2], PALETTE_REQUIRED)
        self.assertEqual(self.source.read_bytes(), original)
        self._pick(4)
        self.assertIsNone(self.window.mode_bar.blocking_reason(self.window))

    def test_the_switch_is_large_and_names_its_state(self):
        switch = self.window.mode_bar.switch
        self.assertIsInstance(switch, QPushButton)
        self.assertTrue(switch.isCheckable())
        self.assertGreaterEqual(switch.minimumHeight(), 44)
        self.assertTrue(switch.text().endswith("OFF"))
        self.assertEqual(load_mode(self.workspace_root), MODE_FULL)
        switch.click()
        self.assertTrue(switch.isChecked())
        self.assertTrue(switch.text().endswith("ON"))
        self.assertEqual(load_mode(self.workspace_root), MODE_VANILLA)
        self.assertTrue(self.window.mode_bar.banner.isVisibleTo(self.window.mode_bar))
        switch.click()
        self.assertTrue(switch.text().endswith("OFF"))
        self.assertEqual(load_mode(self.workspace_root), MODE_FULL)

    def test_hair_cap_and_hidden_hdr_in_the_mode(self):
        tab = self.window.appearance_tab
        mode_then_overbright = (lambda: self._mode(True), lambda: tab.overbright_checkbox.setChecked(True))
        overbright_then_mode = (lambda: tab.overbright_checkbox.setChecked(True), lambda: self._mode(True))
        for first, second in (mode_then_overbright, overbright_then_mode):
            self._mode(False)
            tab.overbright_checkbox.setChecked(False)
            first()
            second()
            self.assertFalse(tab.hdr.isVisibleTo(tab))
        # the last order applied the mode after the check, so overbright is off and the Pick buttons are back
        self.assertFalse(tab.overbright_checkbox.isChecked())
        self.assertTrue(tab.btn_skin_color.isVisibleTo(tab))
        self.assertTrue(tab.btn_hair_color.isVisibleTo(tab))
        self._pick(4)
        for spin, value in zip(tab.hair_hdr_spins, (2.0, 0.5, 0.5)):
            spin.setValue(value)
        self.assertEqual(tab.current_hair_rgb, [2.0, 0.5, 0.5])
        self.assertEqual(self.window.mode_bar.blocking_reason(self.window), HAIR_CAP_REQUIRED)
        tab.hair_hdr_spins[0].setValue(1.1)
        self.assertIsNone(self.window.mode_bar.blocking_reason(self.window))
        self._mode(False)
        self.assertTrue(tab.hdr.isVisibleTo(tab))
        self.assertFalse(tab.overbright_checkbox.isChecked())
        tab.overbright_checkbox.setChecked(True)
        self.assertTrue(all(spin.isEnabledTo(tab.hdr) for spin in tab.skin_hdr_spins))
        for button in (tab.btn_preset_normal, tab.btn_preset_bright, tab.btn_preset_glow, tab.btn_preset_extreme):
            self.assertTrue(button.isVisibleTo(tab.hdr))
        self.assertEqual(tab.hair_hdr_spins[0].maximum(), MAX_HDR_COMPONENT)

    def test_a_loaded_overbright_hair_keeps_its_value_in_the_mode(self):
        tab = self.window.appearance_tab
        self._mode(False)
        tab.overbright_checkbox.setChecked(True)
        for spin, value in zip(tab.hair_hdr_spins, (2.0, 0.5, 0.5)):
            spin.setValue(value)
        self.window.save_save_file()
        saved = self.source.read_bytes()
        self._mode(True)
        self.window.load_save_file(str(self.source))
        self.assertEqual(tab.current_hair_rgb[0], 2.0)
        self.assertFalse(tab.overbright_checkbox.isChecked())
        self.assertFalse(tab.hdr.isVisibleTo(tab))
        self.assertTrue(tab.btn_hair_color.isVisibleTo(tab))
        self.assertEqual(self.window.mode_bar.blocking_reason(self.window), PALETTE_REQUIRED)
        self._pick(4)
        self.assertEqual(self.window.mode_bar.blocking_reason(self.window), HAIR_CAP_REQUIRED)
        self.window.save_save_file()
        self.assertEqual(self.source.read_bytes(), saved)

    def test_a_hair_saved_at_the_cap_reloads_without_a_block(self):
        tab = self.window.appearance_tab
        self._mode(True)
        self._pick(4)
        tab.overbright_checkbox.setChecked(True)
        for spin, value in zip(tab.hair_hdr_spins, (1.1, 0.5, 0.5)):
            spin.setValue(value)
        self.window.save_save_file()
        self.window.load_save_file(str(self.source))
        self.assertEqual(self.window.appearance_tab.current_hair_rgb[0], 1.100000023841858)
        self.assertIsNone(self.window.mode_bar.blocking_reason(self.window))

    def test_rename_follows_the_capitalisation_rule_only_in_the_mode(self):
        self._mode(True)
        self._pick(4)
        self.assertIsNone(self.window.mode_bar.blocking_reason(self.window))
        self.window.misc_tab.name_input.setText("frost wulf")
        reason = self.window.mode_bar.blocking_reason(self.window)
        self.assertIn("capital", reason)
        self.window.save_save_file()
        self.assertEqual(RecordingMessageBox.calls[-1][2], reason)
        self.window.misc_tab.name_input.setText("Frost Wulf")
        self.window.save_save_file()
        self.assertEqual(_fields(compare(str(self.before), str(self.source))), ["container.character_name", "payload.skin_color"])
        shutil.copy(self.before, self.source)
        self.window.load_save_file(str(self.source))
        self._mode(False)
        self.window.misc_tab.name_input.setText("frost wulf")
        self.window.save_save_file()
        self.assertEqual(_fields(compare(str(self.before), str(self.source))), ["container.character_name"])

    def test_the_mode_is_remembered_across_windows(self):
        self._mode(True)
        self.assertEqual(load_mode(self.workspace_root), MODE_VANILLA)
        second = mw.MainWindow(startup_warning=False)
        try:
            self.assertTrue(second.mode_bar.switch.isChecked())
            self.assertTrue(second.skills_tab.read_only)
            self.assertTrue(second.inventory_tab.read_only)
            second.load_save_file(str(self.source))
            self.assertTrue(all(not slot.isEnabledTo(second.inventory_tab) for slot in second.inventory_tab.slots.values()))
        finally:
            dispose(second)

    def test_new_character_dialog_in_the_mode(self):
        folder = Path(self.temp.name) / "newchars"
        folder.mkdir()
        with patch.object(ncd, "candidate_character_directories", return_value=[(folder, "Valheim, local folder")]):
            dialog = NewCharacterDialog(vanilla=True)
            try:
                self.assertEqual([round(c, 3) for c in dialog.skin_color], [round(c, 3) for c in TONES[4]])
                dialog.name_input.setText("frostwulf")
                self.assertFalse(dialog.buttons.button(QDialogButtonBox.Ok).isEnabled())
                dialog.name_input.setText("Frostwulf")
                self.assertTrue(dialog.buttons.button(QDialogButtonBox.Ok).isEnabled())
                with patch.object(SkinPaletteDialog, "pick", return_value=list(TONES[1])):
                    dialog._pick_skin()
                self.assertEqual(dialog.skin_color, list(TONES[1]))
            finally:
                dispose(dialog)
            plain = NewCharacterDialog(vanilla=False)
            try:
                self.assertEqual(plain.skin_color, list(DEFAULT_SKIN))
                plain.name_input.setText("frostwulf")
                self.assertTrue(plain.buttons.button(QDialogButtonBox.Ok).isEnabled())
            finally:
                dispose(plain)

    def test_the_banner_names_the_rules_and_the_attribution(self):
        self._mode(True)
        text = self.window.mode_bar.banner.text()
        for word in ("palette", "1.1", "read-only", "capitalised", "courtesy"):
            self.assertIn(word, text)
        self.assertIn("Monk Skin Tone", editorModeBar.skinPaletteDialog.PALETTE_ATTRIBUTION)
        self.assertIn("CC BY 4.0", editorModeBar.skinPaletteDialog.PALETTE_ATTRIBUTION)


if __name__ == "__main__":
    unittest.main()
