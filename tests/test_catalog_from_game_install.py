"""The committed catalogue equals a fresh generation from the installed game.

Runs only where the game and the optional UnityPy package exist; skips by name otherwise, so
CI (which has neither) never reports a green result it did not earn. Read-only: bundles and
resources.assets are loaded into memory and nothing is written.
"""
import json
import unittest
from pathlib import Path

from subscripts.iconExtraction import default_game_directory, extraction_available
from tools.catalogFromGame import english_names, item_record, localisation_csv, shared_items, steam_build_id

COMMITTED = Path(__file__).resolve().parents[1] / "data" / "valheim_items.json"
COMPARED = ("item_type", "limits", "durability", "damage")


class CatalogueMatchesInstallTests(unittest.TestCase):
    def test_committed_catalogue_matches_a_fresh_generation_from_the_install(self):
        game_dir = default_game_directory()
        if not extraction_available() or game_dir is None:
            self.skipTest("no installed Valheim with UnityPy available on this machine")
        committed = {r["prefab"]: r for r in json.loads(COMMITTED.read_text(encoding="utf-8"))["items"]}
        english = english_names(localisation_csv(game_dir))
        fresh = {}
        for prefab, shared in shared_items(game_dir).items():
            record = item_record(prefab, shared, english)
            if record:
                fresh[prefab] = record
        self.assertEqual(set(fresh), set(committed), "prefab sets differ")
        for prefab, record in fresh.items():
            for key in COMPARED:
                self.assertEqual(record.get(key), committed[prefab].get(key), f"{prefab}.{key}")
        print(f"catalogue matches the install: {len(fresh)} items, build {steam_build_id(game_dir)}")


if __name__ == "__main__":
    unittest.main()
