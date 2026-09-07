import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import subscripts.saveSafety as safety
import ui.mainWindow as mw
from subscripts.saveSafety import DestinationChangedError, SaveVerificationError, replace_verified_save
from subscripts.workspace import (
    BACKUP_RETENTION, SNAPSHOT_RETENTION, WorkspaceError, create_workspace_session, prune_workspace,
)
from tests.fixture_saves import realistic_root_save, write_fch
from tests.qt_support import dispose


APP = QApplication.instance() or QApplication([])


class RecordingMessageBox:
    calls = []
    Warning = 0
    Ok = 0

    def __init__(self, *args, **kwargs):
        pass

    def setInformativeText(self, *a): pass
    def exec(self): return 0

    @classmethod
    def information(cls, *args, **kwargs): cls.calls.append(("info", args[1]))

    @classmethod
    def warning(cls, *args, **kwargs): cls.calls.append(("warn", args[1]))

    @classmethod
    def critical(cls, *args, **kwargs): cls.calls.append(("crit", args[1]))


class BackupIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.destination = write_fch(self.root / "hero.fch", realistic_root_save(name="Hero"))
        self.candidate = write_fch(self.root / "candidate.fch", realistic_root_save(name="Edited"))
        self.original = self.destination.read_bytes()

    def tearDown(self):
        self.temp.cleanup()

    def test_corrupted_backup_refuses_the_replace(self):
        def bad_backup(destination, backup_directory=None):
            path = Path(backup_directory) / "hero.bak"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"not the destination")
            return str(path)
        with patch.object(safety, "create_timestamped_backup", side_effect=bad_backup):
            with self.assertRaises(SaveVerificationError):
                replace_verified_save(str(self.candidate), str(self.destination), backup_directory=str(self.root / "backups"))
        self.assertEqual(self.destination.read_bytes(), self.original)

    def test_good_backup_still_replaces(self):
        backup = replace_verified_save(str(self.candidate), str(self.destination), backup_directory=str(self.root / "backups"))
        self.assertEqual(Path(backup).read_bytes(), self.original)
        self.assertEqual(self.destination.read_bytes(), self.candidate.read_bytes() if self.candidate.exists() else self.destination.read_bytes())

    def test_destination_change_is_a_typed_error(self):
        with self.assertRaises(DestinationChangedError):
            replace_verified_save(str(self.candidate), str(self.destination), expected_destination_sha256="0" * 64)
        self.assertEqual(self.destination.read_bytes(), self.original)


class RetentionTests(unittest.TestCase):
    def test_prune_keeps_the_newest_ten_of_each(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            source, backups = workspace / "source", workspace / "backups"
            source.mkdir(); backups.mkdir()
            for i in range(12):
                for folder, suffix in ((source, "-opened.fch"), (backups, ".bak")):
                    p = folder / f"{i:02d}{suffix}"
                    p.write_bytes(b"x")
                    os.utime(p, (1_700_000_000 + i, 1_700_000_000 + i))
            removed = prune_workspace(workspace)
            self.assertEqual(len(removed), 4)
            self.assertEqual(sorted(p.name for p in source.iterdir())[0], "02-opened.fch")
            self.assertEqual(sorted(p.name for p in backups.iterdir())[0], "02.bak")
            self.assertEqual(len(list(source.iterdir())), SNAPSHOT_RETENTION)
            self.assertEqual(len(list(backups.iterdir())), BACKUP_RETENTION)

    def test_opening_prunes_old_snapshots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save = write_fch(root / "hero.fch", realistic_root_save(name="Hero"))
            session = create_workspace_session(str(save), realistic_root_save(name="Hero"), workspace_root=root / "ws")
            source_dir = Path(session.workspace_dir) / "source"
            for i in range(15):
                p = source_dir / f"old{i:02d}-opened.fch"
                p.write_bytes(b"x")
                os.utime(p, (1_600_000_000 + i, 1_600_000_000 + i))
            create_workspace_session(str(save), realistic_root_save(name="Hero"), workspace_root=root / "ws")
            self.assertEqual(len(list(source_dir.iterdir())), SNAPSHOT_RETENTION)
            self.assertTrue(Path(session.source_snapshot_path).exists())


class TypedRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.save_dir = root / "characters_local"; self.save_dir.mkdir()
        self.source = write_fch(self.save_dir / "hero.fch", realistic_root_save(name="Hero"))
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(mw, "scan_valheim", side_effect=lambda: mw.ValheimScan(state=mw.ScanState.NOT_RUNNING)))
        self.stack.enter_context(patch.object(mw, "discover_character_records", return_value=[]))
        self.stack.enter_context(patch.object(mw, "QMessageBox", RecordingMessageBox))
        self.stack.enter_context(patch("subscripts.workspace.default_workspace_root", return_value=root / "workspace"))
        RecordingMessageBox.calls = []
        self.window = mw.MainWindow(startup_warning=False)
        self.window.load_save_file(str(self.source))

    def tearDown(self):
        dispose(self.window)
        self.window = None
        self.stack.close()
        self.temp.cleanup()

    def test_destination_change_routes_to_the_external_change_status(self):
        self.window.workspace_session.expected_source_sha256 = "0" * 64
        with patch.object(self.window.workspace_session, "assert_source_unchanged"):
            self.window.save_save_file()
        self.assertEqual(RecordingMessageBox.calls[-1][0], "crit")
        self.assertIn("Changed Outside", RecordingMessageBox.calls[-1][1])
        self.assertEqual(self.window.save_status.state_label.text(), "Needs attention")

    def test_workspace_error_gets_its_own_title(self):
        with patch.object(mw, "store_verified_working_copy", side_effect=WorkspaceError("disk full")):
            self.window.save_save_file()
        self.assertEqual(RecordingMessageBox.calls[-1], ("crit", "Workspace or File Error"))


if __name__ == "__main__":
    unittest.main()
