import json
import logging
import os
import tempfile
import unittest
from pathlib import Path

from subscripts.workspace import _character_id
from subscripts.workspaceConsolidation import consolidate_workspaces


PLAYER_ID = 35886264


def _old_pair_dir(active: Path, name: str, stamp: int, working_mtime: float, snapshot: str = "20260909T212622Z-opened.fch"):
    """A directory named the pre-phase-45 way, with a snapshot, a working copy, a backup and metadata."""
    directory = active / f"{name}-{stamp:012x}"
    for sub in ("source", "working", "backups"):
        (directory / sub).mkdir(parents=True)
    (directory / "source" / snapshot).write_bytes(b"snapshot " + str(stamp).encode())
    working = directory / "working" / "character.fch"
    working.write_bytes(b"working " + str(stamp).encode())
    os.utime(working, (working_mtime, working_mtime))
    (directory / "backups" / f"hero.fch.{stamp}.bak").write_bytes(b"backup")
    metadata = {
        "character_id": directory.name, "character_name": name, "player_id": PLAYER_ID, "state": "active",
        "workspace_dir": str(directory), "source_snapshot_path": str(directory / "source" / snapshot),
        "working_path": str(working), "backups_dir": str(directory / "backups"),
        "metadata_path": str(directory / "metadata.json"), "last_backup_path": str(directory / "backups" / "x.bak"),
    }
    (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return directory


class WorkspaceConsolidationTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.active = self.root / "characters" / "active"
        self.target = self.active / _character_id("Fenrir", PLAYER_ID)

    def tearDown(self):
        self._temp.cleanup()

    def test_two_old_pair_directories_merge_into_the_identity_directory(self):
        older = _old_pair_dir(self.active, "Fenrir", 1788989181, working_mtime=1_700_000_000, snapshot="a-opened.fch")
        newer = _old_pair_dir(self.active, "Fenrir", 1788926400, working_mtime=1_700_000_500, snapshot="b-opened.fch")
        (older / "working" / ".candidate.fch.tmp").write_bytes(b"half written")

        moved = consolidate_workspaces(self.root)

        self.assertEqual(sorted(old for old, _ in moved), sorted([older, newer]))
        self.assertTrue(all(new == self.target for _, new in moved))
        self.assertFalse(older.exists())
        self.assertFalse(newer.exists())
        self.assertEqual(sorted(p.name for p in (self.target / "source").iterdir()), ["a-opened.fch", "b-opened.fch"])
        self.assertEqual((self.target / "working" / "character.fch").read_bytes(), b"working 1788926400")
        backups = sorted(p.name for p in (self.target / "backups").iterdir())
        self.assertEqual(len([n for n in backups if n.endswith(".consolidated.bak")]), 1)
        self.assertEqual(len([n for n in backups if n.startswith("metadata.") and n.endswith(".superseded.json")]), 1)
        self.assertIn(".candidate.fch.tmp", backups)
        self.assertEqual(len([n for n in backups if n.endswith(".bak") and ".consolidated" not in n]), 2)
        metadata = json.loads((self.target / "metadata.json").read_text(encoding="utf-8"))
        for field in ("workspace_dir", "source_snapshot_path", "working_path", "backups_dir", "metadata_path", "last_backup_path"):
            self.assertTrue(metadata[field].startswith(str(self.target)), (field, metadata[field]))
            self.assertFalse(metadata[field].startswith(str(older)) or metadata[field].startswith(str(newer)), field)
        self.assertTrue(Path(metadata["source_snapshot_path"]).is_file())

    def test_consolidation_is_idempotent_and_skips_directories_without_an_identity(self):
        _old_pair_dir(self.active, "Fenrir", 1788989181, working_mtime=1_700_000_000)
        orphan = self.active / "Ghost-000000000000"
        orphan.mkdir(parents=True)
        (orphan / "metadata.json").write_text(json.dumps({"character_name": "Ghost", "player_id": None}), encoding="utf-8")

        first = consolidate_workspaces(self.root)
        second = consolidate_workspaces(self.root)

        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertTrue(orphan.is_dir())
        self.assertTrue(self.target.is_dir())

    def test_name_collisions_get_numbered_suffixes(self):
        _old_pair_dir(self.active, "Fenrir", 1788989181, working_mtime=1_700_000_000, snapshot="same.fch")
        _old_pair_dir(self.active, "Fenrir", 1788926400, working_mtime=1_700_000_500, snapshot="same.fch")

        consolidate_workspaces(self.root)

        self.assertEqual(sorted(p.name for p in (self.target / "source").iterdir()), ["same-1.fch", "same.fch"])

    def test_malformed_metadata_and_a_missing_root_are_tolerated(self):
        self.assertEqual(consolidate_workspaces(self.root), [])
        self.assertFalse(self.active.exists())
        broken = self.active / "Broken-000000000001"
        broken.mkdir(parents=True)
        (broken / "metadata.json").write_text("{not json", encoding="utf-8")
        listed = self.active / "Listed-000000000002"
        listed.mkdir()
        (listed / "metadata.json").write_text("[1, 2]", encoding="utf-8")
        _old_pair_dir(self.active, "Fenrir", 1788989181, working_mtime=1_700_000_000)

        with self.assertLogs("subscripts.workspaceConsolidation", level=logging.WARNING) as caught:
            moved = consolidate_workspaces(self.root)

        self.assertEqual(len([line for line in caught.output if "WARNING" in line]), 2)
        self.assertTrue(broken.is_dir())
        self.assertTrue(listed.is_dir())
        self.assertEqual(len(moved), 1)
        self.assertTrue(self.target.is_dir())


if __name__ == "__main__":
    unittest.main()
