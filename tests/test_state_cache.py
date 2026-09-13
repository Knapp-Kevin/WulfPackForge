import json
import tempfile
import unittest
from pathlib import Path

from subscripts.stateCache import CACHE_BUILD_KEY, StateCache


FIELDS = {"name": "Ares", "player_id": 111, "date_created": 1, "version": 46, "valid": True, "error": None}


def _write_cache(path: Path, build: str, entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 2, "build": build, "entries": entries}), encoding="utf-8")


class StateCacheTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.path = Path(self._temp.name) / "index" / "states.json"

    def tearDown(self):
        self._temp.cleanup()

    def test_a_verdict_from_another_build_is_not_trusted(self):
        entry = {"size": 10, "mtime_ns": 5, "fields": FIELDS}
        _write_cache(self.path, "container:40 payload:29.106.2", {"c:/saves/ares.fch": entry})
        self.assertIsNone(StateCache(self.path).lookup("c:/saves/ares.fch", 10, 5))
        _write_cache(self.path, CACHE_BUILD_KEY, {"c:/saves/ares.fch": entry})
        self.assertEqual(StateCache(self.path).lookup("c:/saves/ares.fch", 10, 5), FIELDS)

    def test_paths_not_seen_this_scan_are_dropped_on_save(self):
        entry = {"size": 10, "mtime_ns": 5, "fields": FIELDS}
        _write_cache(self.path, CACHE_BUILD_KEY, {"c:/saves/ares.fch": entry, "c:/saves/gone.fch": entry})
        cache = StateCache(self.path)
        self.assertEqual(cache.lookup("c:/saves/ares.fch", 10, 5), FIELDS)
        cache.save()
        written = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(list(written["entries"]), ["c:/saves/ares.fch"])
        self.assertEqual(written["build"], CACHE_BUILD_KEY)
        self.assertEqual(written["schema_version"], 2)

    def test_build_key_names_both_supported_sets(self):
        self.assertIn("46", CACHE_BUILD_KEY)
        self.assertIn("33.109.2", CACHE_BUILD_KEY)
        self.assertNotIn("33.109.2", StateCache(None, build_key="other").build_key)


if __name__ == "__main__":
    unittest.main()
