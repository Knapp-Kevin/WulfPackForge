import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import subscripts.characterRecords as records_module
from subscripts.characterRecords import (
    StateCache, build_records, classify_path, discover_character_records, find_state, scan_states,
)
from subscripts.workspace import create_workspace_session
from tests.fixture_saves import realistic_root_save, write_fch
from ui.characterPicker import CharacterPickerBar


APP = QApplication.instance() or QApplication([])


def lineage(directory: Path):
    """Three files of one identity plus one of another, with distinct mtimes."""
    ares = realistic_root_save(name="Ares")
    ares["player_id"], ares["date_created_unix"] = 111, 1700000000
    other = realistic_root_save(name="Njord")
    other["player_id"], other["date_created_unix"] = 222, 1700000001
    files = [
        write_fch(directory / "ares_backup_auto-20260101.fch", ares),
        write_fch(directory / "ares.fch.old", ares),
        write_fch(directory / "ares.fch", ares),
        write_fch(directory / "njord.fch", other),
    ]
    for offset, path in enumerate(files):
        os.utime(path, (1_700_000_000 + offset * 60, 1_700_000_000 + offset * 60))
    return files


class CharacterRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.save_dir = self.home / ".config" / "unity3d" / "IronGate" / "Valheim" / "characters_local"
        self.save_dir.mkdir(parents=True)
        self.workspace = self.home / "workspace"

    def tearDown(self):
        self.temp.cleanup()

    def test_states_of_one_identity_form_one_record_with_the_active_head(self):
        lineage(self.save_dir)
        (self.save_dir / "broken.fch").write_bytes(b"garbage")
        records = discover_character_records(home=self.home, system_name="Linux", workspace_root=self.workspace)
        by_name = {r.name: r for r in records}
        self.assertEqual(set(by_name), {"Ares", "Njord", "broken"})
        ares = by_name["Ares"]
        self.assertEqual(len(ares.states), 3)
        self.assertEqual([s.kind for s in ares.states], ["active", "game-old", "game-backup"])  # newest first
        self.assertEqual(Path(ares.head.path).name, "ares.fch")
        self.assertFalse(by_name["broken"].valid)
        self.assertEqual(records[-1].name, "broken")  # invalid records sort last

    def test_classify_covers_game_and_workspace_locations(self):
        ws = self.workspace
        self.assertEqual(classify_path(self.save_dir / "hero.fch", ws), "active")
        self.assertEqual(classify_path(self.save_dir / "hero.fch.old", ws), "game-old")
        self.assertEqual(classify_path(self.save_dir / "hero_backup_auto-1.fch", ws), "game-backup")
        self.assertEqual(classify_path(ws / "characters" / "active" / "x" / "source" / "a-opened.fch", ws), "workspace-snapshot")
        self.assertEqual(classify_path(ws / "characters" / "active" / "x" / "backups" / "hero.fch.1.bak", ws), "workspace-backup")
        self.assertEqual(classify_path(ws / "characters" / "active" / "x" / "working" / "character.fch", ws), "workspace-working")

    def test_second_scan_uses_the_cache_instead_of_verifying_again(self):
        lineage(self.save_dir)
        cache = StateCache(self.workspace / "index" / "states.json")
        with patch.object(records_module, "verify_fch_round_trip", wraps=records_module.verify_fch_round_trip) as spy:
            scan_states(home=self.home, system_name="Linux", workspace_root=self.workspace, cache=cache)
            first = spy.call_count
            scan_states(home=self.home, system_name="Linux", workspace_root=self.workspace, cache=cache)
            self.assertEqual(spy.call_count, first)
        self.assertGreater(first, 0)
        self.assertTrue((self.workspace / "index" / "states.json").is_file())

    def test_workspace_is_keyed_by_identity_not_path(self):
        active, old, *_ = lineage(self.save_dir)
        root = realistic_root_save(name="Ares")
        root["player_id"], root["date_created_unix"] = 111, 1700000000
        a = create_workspace_session(str(active), root, workspace_root=self.workspace)
        b = create_workspace_session(str(old), root, workspace_root=self.workspace)
        self.assertEqual(a.workspace_dir, b.workspace_dir)
        records = discover_character_records(home=self.home, system_name="Linux", workspace_root=self.workspace)
        ares = next(r for r in records if r.name == "Ares")
        self.assertIn("workspace-snapshot", {s.kind for s in ares.states})
        self.assertEqual(Path(ares.head.path).name, "ares.fch")

    def test_picker_lists_records_and_resolves_state_metadata(self):
        lineage(self.save_dir)
        records = discover_character_records(home=self.home, system_name="Linux", workspace_root=self.workspace)
        picker = CharacterPickerBar(discover=lambda: records)
        picker.refresh(None)
        labels = [picker.character_combo.itemText(i) for i in range(picker.character_combo.count())]
        self.assertEqual(len(labels), 2)
        self.assertTrue(any(label.startswith("Ares — 3 states") for label in labels), labels)
        old_path = str(self.save_dir / "ares.fch.old")
        source, modified = picker.metadata_for(old_path)
        self.assertEqual(source, "Local")
        self.assertIsNotNone(modified)
        record, state = find_state(records, old_path)
        self.assertEqual((record.name, state.kind), ("Ares", "game-old"))


if __name__ == "__main__":
    unittest.main()
