import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from subscripts.playerDataUtil import unpack_player_data_hex
from subscripts.saveSafety import verify_fch_round_trip
from tests.fixture_saves import realistic_player_data, realistic_root_save, write_fch
from subscripts.playerDataUtil import pack_player_data_hex
from ui import mainWindow as mw
from subscripts.valheim_detection import ScanState, ValheimScan


APP = QApplication.instance() or QApplication([])


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
    def information(cls, *args, **kwargs):
        cls.calls.append(("info", args[1]))

    @classmethod
    def warning(cls, *args, **kwargs):
        cls.calls.append(("warn", args[1]))

    @classmethod
    def critical(cls, *args, **kwargs):
        cls.calls.append(("crit", args[1]))


class MainWindowSaveFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.save_dir = root / "characters_local"
        self.save_dir.mkdir()
        self.source = write_fch(self.save_dir / "hero.fch", realistic_root_save())
        self.original = self.source.read_bytes()
        self.workspace_root = root / "workspace"
        RecordingMessageBox.calls = []
        self.scan = ValheimScan(state=ScanState.NOT_RUNNING)

        self.stack = ExitStack()
        self.stack.enter_context(patch.object(mw, "scan_valheim", side_effect=lambda: self.scan))
        self.stack.enter_context(patch.object(mw, "discover_character_saves", return_value=[]))
        self.stack.enter_context(patch.object(mw, "QMessageBox", RecordingMessageBox))
        self.stack.enter_context(
            patch("subscripts.workspace.default_workspace_root", return_value=self.workspace_root)
        )
        self.window = mw.MainWindow()
        self.window.load_save_file(str(self.source))

    def tearDown(self):
        self.window.close()
        self.stack.close()
        self.temp.cleanup()

    def _backups(self):
        return sorted(self.workspace_root.rglob("*.bak*"))

    def test_noop_save_is_byte_identical(self):
        self.assertTrue(self.window.btn_save_save.isEnabled())
        self.window.save_save_file()
        self.assertEqual(RecordingMessageBox.calls[-1][0], "info")
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(len(self._backups()), 1)

    def test_rename_is_applied_and_backed_up(self):
        self.window.misc_tab.name_input.setText("Renamed")
        self.window.save_save_file()
        parsed = verify_fch_round_trip(str(self.source))
        self.assertEqual(parsed["character_name"], "Renamed")
        payload = unpack_player_data_hex(parsed["player_data_hex"])
        self.assertEqual([s["id"] for s in payload["skills"]], [1, 500])
        self.assertEqual(len(payload["foods"]), 4)
        self.assertEqual(len(self._backups()), 1)

    def test_external_change_blocks_replacement(self):
        write_fch(self.source, realistic_root_save(name="External"))
        external = self.source.read_bytes()
        self.window.save_save_file()
        self.assertEqual(self.source.read_bytes(), external)
        self.assertEqual(RecordingMessageBox.calls[-1][0], "crit")
        self.assertEqual(self.window.save_status.state_label.text(), "Needs attention")

    def test_inconclusive_scan_keeps_destination_and_stores_working_copy(self):
        self.window.misc_tab.name_input.setText("Renamed")
        self.scan = ValheimScan(state=ScanState.INCONCLUSIVE, detail="1 process could not be identified")
        with patch.object(mw.tempfile, "NamedTemporaryFile", wraps=tempfile.NamedTemporaryFile) as spy:
            self.window.save_save_file()
        staged_dirs = [os.path.normcase(str(c.kwargs.get("dir", ""))) for c in spy.call_args_list]
        self.assertNotIn(os.path.normcase(str(self.save_dir)), staged_dirs)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(self._backups(), [])
        self.assertEqual(RecordingMessageBox.calls[-1][0], "warn")
        working = verify_fch_round_trip(self.window.workspace_session.working_path)
        self.assertEqual(working["character_name"], "Renamed")
        self.assertEqual(self.window.save_status.state_label.text(), "Verified")
        self.assertTrue(self.window.btn_save_save.isEnabled())

        self.scan = ValheimScan(state=ScanState.NOT_RUNNING)
        self.window.save_save_file()
        self.assertEqual(verify_fch_round_trip(str(self.source))["character_name"], "Renamed")

    def test_new_character_button_creates_and_opens_a_verified_file(self):
        from subscripts.newCharacter import NewCharacterSpec

        spec = NewCharacterSpec(name="Sigrun", directory=str(self.save_dir), model_index=1,
                                hair="Hair7", beard="BeardNone",
                                skin_color=[0.5, 0.5, 0.5], hair_color=[0.1, 0.2, 0.3])

        class FakeDialog:
            def __init__(self, *args, **kwargs):
                pass

            def exec(self):
                return 1

            def result_spec(self):
                return spec

        with patch.object(mw, "NewCharacterDialog", FakeDialog):
            self.window.create_new_character()

        created = self.save_dir / "sigrun.fch"
        self.assertTrue(created.is_file())
        self.assertEqual(os.path.normcase(self.window.current_fch), os.path.normcase(str(created)))
        self.assertEqual(self.window.save_status.state_label.text(), "Verified")
        payload = unpack_player_data_hex(verify_fch_round_trip(str(created))["player_data_hex"])
        self.assertEqual((payload["model_index"], payload["hair"], payload["beard"]), (1, "Hair7", "BeardNone"))
        original = created.read_bytes()
        self.window.save_save_file()
        self.assertEqual(created.read_bytes(), original)

    def test_smoke_mode_skips_startup_dialog_when_valheim_runs(self):
        self.scan = ValheimScan(state=ScanState.RUNNING, process={"pid": 1, "name": "valheim.exe", "exe": None})
        RecordingMessageBox.calls = []
        quiet = mw.MainWindow(startup_warning=False)
        self.assertNotIn(("startup", "constructed"), RecordingMessageBox.calls)
        quiet.close()
        loud = mw.MainWindow()
        self.assertIn(("startup", "constructed"), RecordingMessageBox.calls)
        loud.close()

    def test_unsupported_inner_version_is_read_only(self):
        payload = realistic_player_data()
        payload["version"] = 30
        other = write_fch(self.save_dir / "other.fch", realistic_root_save(pack_player_data_hex(payload)))
        self.window.load_save_file(str(other))
        self.assertEqual(self.window.save_status.state_label.text(), "Compatibility unverified")
        self.assertFalse(self.window.btn_save_save.isEnabled())


if __name__ == "__main__":
    unittest.main()
