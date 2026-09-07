import json
import tempfile
import unittest
from pathlib import Path

from subscripts.fchUtil import compile_fch
from subscripts.workspace import (
    SourceChangedError,
    create_workspace_session,
    file_sha256,
    store_verified_working_copy,
)


def minimal_save_data(name="Frostwulf"):
    return {
        "version": 43,
        "stats": [],
        "first_spawn": True,
        "worlds": [],
        "character_name": name,
        "player_id": 987654,
        "start_seed": "workspace-test",
        "used_cheats": False,
        "date_created_unix": 0,
        "known_worlds": {},
        "known_world_keys": {},
        "known_commands": {},
        "enemy_stats": {},
        "item_pickup_stats": {},
        "item_craft_stats": {},
        "player_data_hex": None,
    }


def compile_save(directory: Path, save_data: dict, filename="source.fch") -> Path:
    wrapper = directory / f"{filename}.json"
    output = directory / filename
    wrapper.write_text(json.dumps(save_data), encoding="utf-8")
    compile_fch(str(wrapper), str(output))
    return output


class WorkspaceTests(unittest.TestCase):
    def test_open_creates_immutable_snapshot_working_copy_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source-files"
            workspace_root = root / "workspace"
            source_dir.mkdir()
            save_data = minimal_save_data()
            source = compile_save(source_dir, save_data)
            source_hash = file_sha256(source)

            session = create_workspace_session(str(source), save_data, workspace_root=workspace_root)

            self.assertEqual(session.opened_sha256, source_hash)
            self.assertEqual(session.expected_source_sha256, source_hash)
            self.assertTrue(Path(session.source_snapshot_path).is_file())
            self.assertTrue(Path(session.working_path).is_file())
            self.assertTrue(Path(session.metadata_path).is_file())
            self.assertEqual(file_sha256(session.source_snapshot_path), source_hash)
            self.assertEqual(file_sha256(session.working_path), source_hash)
            self.assertIn("characters", Path(session.workspace_dir).parts)
            self.assertIn("active", Path(session.workspace_dir).parts)

    def test_surrogate_escaped_character_name_persists_in_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            save_data = minimal_save_data(name=b"Fr\xffst".decode("utf-8", "surrogateescape"))
            source = compile_save(root, save_data)

            session = create_workspace_session(str(source), save_data, workspace_root=root / "workspace")

            metadata = json.loads(Path(session.metadata_path).read_text(encoding="utf-8"))
            self.assertEqual(metadata["character_name"], save_data["character_name"])

    def test_external_source_change_is_detected_without_touching_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            save_data = minimal_save_data()
            source = compile_save(root, save_data)
            session = create_workspace_session(str(source), save_data, workspace_root=root / "workspace")
            snapshot_hash = file_sha256(session.source_snapshot_path)

            source.write_bytes(source.read_bytes() + b"external-change")

            self.assertFalse(session.source_matches_expected())
            with self.assertRaises(SourceChangedError):
                session.assert_source_unchanged()
            self.assertEqual(file_sha256(session.source_snapshot_path), snapshot_hash)

    def test_verified_candidate_updates_working_copy_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            initial = minimal_save_data()
            source = compile_save(root, initial, "active.fch")
            source_hash = file_sha256(source)
            session = create_workspace_session(str(source), initial, workspace_root=root / "workspace")

            edited = minimal_save_data("Fenrir")
            candidate_dir = root / "candidate"
            candidate_dir.mkdir()
            candidate = compile_save(candidate_dir, edited, "edited.fch")
            candidate_hash = file_sha256(candidate)

            store_verified_working_copy(str(candidate), session, expected_root=edited)

            self.assertEqual(file_sha256(session.working_path), candidate_hash)
            self.assertEqual(session.working_sha256, candidate_hash)
            self.assertEqual(file_sha256(source), source_hash)


if __name__ == "__main__":
    unittest.main()
