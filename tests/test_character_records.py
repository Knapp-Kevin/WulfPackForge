import os
import tempfile
import unittest
from tests.qt_support import QtTestCase
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import subscripts.characterRecords as records_module
from subscripts.characterRecords import classify_path, discover_character_records, find_state, scan_states
from subscripts.stateCache import StateCache
from subscripts.workspace import create_workspace_session
from tests.fixture_saves import realistic_root_save, write_fch
from ui.characterPicker import CharacterPickerBar


APP = QApplication.instance() or QApplication([])


def lineage(directory: Path):
    """Three files of one identity plus one of another, with distinct mtimes.

    The backup carries the exact-second creation stamp and the newer files the game's
    midnight rewrite of it, the way Valheim 1.0 leaves a real character's files.
    """
    ares = realistic_root_save(name="Ares")
    ares["player_id"], ares["date_created_unix"] = 111, 1700000000
    rewritten = dict(ares, date_created_unix=1699999999)
    other = realistic_root_save(name="Njord")
    other["player_id"], other["date_created_unix"] = 222, 1700000000
    files = [
        write_fch(directory / "ares_backup_auto-20260101.fch", ares),
        write_fch(directory / "ares.fch.old", rewritten),
        write_fch(directory / "ares.fch", rewritten),
        write_fch(directory / "njord.fch", other),
    ]
    for offset, path in enumerate(files):
        os.utime(path, (1_700_000_000 + offset * 60, 1_700_000_000 + offset * 60))
    return files


class CharacterRecordTests(QtTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.save_dir = self.home / ".config" / "unity3d" / "IronGate" / "Valheim" / "characters_local"
        self.save_dir.mkdir(parents=True)
        self.workspace = self.home / "workspace"

    def tearDown(self):
        super().tearDown()  # dispose widgets before the temp directory they scanned goes away
        self.temp.cleanup()

    def test_states_with_one_player_id_and_two_creation_stamps_form_one_record(self):
        lineage(self.save_dir)
        (self.save_dir / "broken.fch").write_bytes(b"garbage")
        records = discover_character_records(home=self.home, system_name="Linux", workspace_root=self.workspace)
        by_name = {r.name: r for r in records}
        self.assertEqual(set(by_name), {"Ares", "Njord", "broken"})
        ares = by_name["Ares"]
        self.assertEqual(len(ares.states), 3)
        self.assertEqual({s.date_created for s in ares.states}, {1700000000, 1699999999})
        self.assertEqual([s.kind for s in ares.states], ["active", "game-old", "game-backup"])  # newest first
        self.assertEqual(Path(ares.head.path).name, "ares.fch")
        self.assertEqual(len(by_name["Njord"].states), 1)  # same stamp as Ares' backup, another id
        self.assertFalse(by_name["broken"].valid)
        self.assertEqual(records[-1].name, "broken")  # invalid records sort last

    def test_the_head_of_a_record_is_the_newest_active_file_across_folders_and_says_so(self):
        local_dir = self.home / "AppData" / "LocalLow" / "IronGate" / "Valheim" / "characters_local"
        cloud_dir = self.home / "SteamRoot" / "userdata" / "1" / "892970" / "remote" / "characters"
        local_dir.mkdir(parents=True)
        cloud_dir.mkdir(parents=True)
        root = realistic_root_save(name="Fenrir")
        root["player_id"], root["date_created_unix"] = 35886264, 1788926400
        local = write_fch(local_dir / "fenrir.fch", root)
        cloud = write_fch(cloud_dir / "fenrir.fch", root)
        os.utime(local, (1_700_000_000, 1_700_000_000))
        os.utime(cloud, (1_700_000_600, 1_700_000_600))
        with patch.dict(os.environ, {"STEAM_DIR": str(self.home / "SteamRoot"), "PROGRAMFILES": str(self.home),
                                     "PROGRAMFILES(X86)": str(self.home)}), \
                patch("subscripts.characterDiscovery.registry_steam_path", return_value=None):
            records = discover_character_records(home=self.home, system_name="Windows", workspace_root=self.workspace)
        (fenrir,) = records
        self.assertEqual(Path(fenrir.head.path), cloud.resolve())
        self.assertIn("Active save (Valheim, Steam Cloud folder)", fenrir.display_label)
        older = next(s for s in fenrir.states if Path(s.path) == local.resolve())
        self.assertEqual(older.where, "Active save (Valheim, local folder)")

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
        b = create_workspace_session(str(old), dict(root, date_created_unix=1699999999), workspace_root=self.workspace)
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
        picker.wait_for_scan()
        labels = [picker.character_combo.itemText(i) for i in range(picker.character_combo.count())]
        self.assertEqual(len(labels), 2)
        self.assertTrue(any(label.startswith("Ares — 3 states") for label in labels), labels)
        old_path = str(self.save_dir / "ares.fch.old")
        where, modified = picker.metadata_for(old_path)
        self.assertEqual(where, "Valheim previous save (Valheim, local folder)")
        self.assertIsNotNone(modified)
        record, state = find_state(records, old_path)
        self.assertEqual((record.name, state.kind), ("Ares", "game-old"))


class PickerRefusesWhatOpenCannotRead(QtTestCase):
    """The picker must not offer a character the open path would reject."""

    def test_identity_fields_reports_invalid_for_an_unreadable_payload(self):
        from tests.fixture_saves import realistic_player_data, realistic_root_save, write_fch
        from subscripts.playerDataUtil import pack_player_data_hex

        packed = pack_player_data_hex(realistic_player_data())
        stamped = (34).to_bytes(4, "little", signed=True).hex() + packed[8:80]
        root = realistic_root_save(player_hex=stamped)
        with tempfile.TemporaryDirectory() as tmp:
            path = write_fch(Path(tmp) / "future.fch", root)
            fields = records_module._identity_fields(Path(path))
        self.assertFalse(fields["valid"])
        self.assertIn("34", fields["error"])


if __name__ == "__main__":
    unittest.main()
