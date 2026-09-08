import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import subscripts.characterDiscovery as discovery
from subscripts.characterDiscovery import candidate_character_directories, discover_character_saves
from subscripts.fchUtil import compile_fch


def minimal_save_data(name="TestViking"):
    return {
        "version": 43,
        "stats": [],
        "first_spawn": True,
        "worlds": [],
        "character_name": name,
        "player_id": 1234,
        "start_seed": "test-seed",
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


def write_save(path: Path, name: str):
    wrapper = path.with_suffix(".json")
    wrapper.write_text(json.dumps(minimal_save_data(name)), encoding="utf-8")
    compile_fch(str(wrapper), str(path))
    wrapper.unlink()


class CharacterDiscoveryTests(unittest.TestCase):
    def test_windows_local_and_cloud_directories_are_discovered(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            local_dir = home / "AppData" / "LocalLow" / "IronGate" / "Valheim" / "characters_local"
            cloud_dir = home / "SteamRoot" / "userdata" / "123456" / "892970" / "remote" / "characters"
            local_dir.mkdir(parents=True)
            cloud_dir.mkdir(parents=True)

            previous = os.environ.get("STEAM_DIR")
            os.environ["STEAM_DIR"] = str(home / "SteamRoot")
            try:
                directories = candidate_character_directories(home=home, system_name="Windows")
            finally:
                if previous is None:
                    os.environ.pop("STEAM_DIR", None)
                else:
                    os.environ["STEAM_DIR"] = previous

            self.assertIn((local_dir.resolve(), "Local"), directories)
            self.assertIn((cloud_dir.resolve(), "Steam Cloud (local copy)"), directories)

    def test_registry_steam_path_is_searched_on_windows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            cloud_dir = home / "OtherDrive" / "steam" / "userdata" / "42" / "892970" / "remote" / "characters_local"
            cloud_dir.mkdir(parents=True)
            with patch.object(discovery, "registry_steam_path", return_value=home / "OtherDrive" / "steam"):
                directories = candidate_character_directories(home=home, system_name="Windows")
            self.assertIn((cloud_dir.resolve(), "Steam local copy"), directories)
            with patch.object(discovery, "registry_steam_path", return_value=None):
                directories = candidate_character_directories(home=home, system_name="Windows")
            self.assertNotIn((cloud_dir.resolve(), "Steam local copy"), directories)

    def test_steam_roots_per_platform(self):
        home = Path("/Users/viking")
        self.assertEqual(discovery.steam_roots(home, "Darwin"), [home / "Library" / "Application Support" / "Steam"])
        self.assertEqual(discovery.steam_roots(home, "Linux"), [home / ".steam" / "steam", home / ".local" / "share" / "Steam"])
        with patch.object(discovery, "registry_steam_path", return_value=Path("G:/Steam")), patch.dict(os.environ, {"STEAM_DIR": "D:/AltSteam"}):
            roots = discovery.steam_roots(home, "Windows")
        self.assertEqual(roots[0], Path("G:/Steam"))
        self.assertEqual(roots[-1], Path("D:/AltSteam"))

    def test_registry_lookup_tolerates_a_missing_key(self):
        try:
            import winreg
        except ImportError:
            self.skipTest("winreg is Windows only")
        with patch.object(winreg, "OpenKey", side_effect=FileNotFoundError):
            self.assertIsNone(discovery.registry_steam_path())
        with patch.object(winreg, "OpenKey"), patch.object(winreg, "QueryValueEx", return_value=("", winreg.REG_SZ)):
            self.assertIsNone(discovery.registry_steam_path())
        with patch.object(winreg, "OpenKey"), patch.object(winreg, "QueryValueEx", return_value=("g:/steam", winreg.REG_SZ)):
            self.assertEqual(discovery.registry_steam_path(), Path("g:/steam"))

    def test_discovery_returns_verified_character_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            local_dir = home / ".config" / "unity3d" / "IronGate" / "Valheim" / "characters_local"
            local_dir.mkdir(parents=True)
            save_path = local_dir / "kevin.fch"
            write_save(save_path, "Kevin")

            results = discover_character_saves(home=home, system_name="Linux")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].name, "Kevin")
            self.assertEqual(results[0].source, "Local")
            self.assertTrue(results[0].valid)
            self.assertEqual(results[0].version, 43)

    def test_truncated_player_payload_is_listed_but_marked_invalid(self):
        from tests.fixture_saves import realistic_player_hex, realistic_root_save, write_fch

        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            local_dir = home / ".config" / "unity3d" / "IronGate" / "Valheim" / "characters_local"
            local_dir.mkdir(parents=True)
            write_fch(local_dir / "cut.fch", realistic_root_save(realistic_player_hex()[:-40]))

            results = discover_character_saves(home=home, system_name="Linux")

            self.assertEqual(len(results), 1)
            self.assertFalse(results[0].valid)
            self.assertIsNotNone(results[0].error)

    def test_corrupt_character_is_listed_but_marked_invalid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            local_dir = home / ".config" / "unity3d" / "IronGate" / "Valheim" / "characters_local"
            local_dir.mkdir(parents=True)
            bad_path = local_dir / "broken.fch"
            bad_path.write_bytes(b"not-a-valid-save")

            results = discover_character_saves(home=home, system_name="Linux")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].name, "broken")
            self.assertFalse(results[0].valid)
            self.assertIsNotNone(results[0].error)


if __name__ == "__main__":
    unittest.main()
