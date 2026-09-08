import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from data.items import ITEMS_BY_PREFAB, ItemDefinition, register_items, resolve_item
from data.skills import VALHEIM_SKILLS
from subscripts import modItems, modOverride, modScan
from subscripts.modProfiles import ModProfile, discover_profiles, profile_from_directory
from subscripts.stableHash import skill_id_for, stable_hash_code


def _utf16(*texts):
    return b"\x00\x01".join(t.encode("utf-16-le") + b"\x00\x00" for t in texts)


def _profile(root: Path, name="Test") -> ModProfile:
    (root / "BepInEx" / "plugins").mkdir(parents=True, exist_ok=True)
    (root / "BepInEx" / "config").mkdir(parents=True, exist_ok=True)
    return ModProfile(name, root / "BepInEx")


class StableHashTests(unittest.TestCase):
    def test_matches_ids_recorded_by_real_skill_mods(self):
        self.assertEqual(stable_hash_code("Sailing"), 2143840399)
        self.assertEqual(stable_hash_code("PackHorse"), -1443093080)
        self.assertEqual(skill_id_for("PackHorse"), 1443093080)
        self.assertEqual(skill_id_for("midnightsfx.hauling"), 924814679)
        self.assertEqual(skill_id_for("Dual Axes"), 82511965)
        self.assertEqual(VALHEIM_SKILLS[110], "Ride")


class ModScanTests(unittest.TestCase):
    def test_identifiers_are_recovered_from_dll_strings(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = _profile(Path(temp))
            (profile.plugins_dir / "Sailing.dll").write_bytes(b"MZ" + _utf16("Sailing", "path/with/slash", " padded", "Dual Axes"))
            found = modScan.identifier_hashes(modScan.plugin_dlls(profile.plugins_dir))
            self.assertEqual(found[2143840399], "Sailing")
            self.assertEqual(found[82511965], "Dual Axes")
            self.assertNotIn(skill_id_for("path/with/slash"), found)
            self.assertNotIn(skill_id_for(" padded"), found)

    def test_localisation_and_display_names(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = _profile(Path(temp))
            (profile.config_dir / "Armory" / "localizations").mkdir(parents=True)
            (profile.config_dir / "Armory" / "localizations" / "English.json").write_text(json.dumps({"item_crossbow_moder": "Dragonfrost Crossbow"}), encoding="utf-8")
            (profile.config_dir / "Armory" / "localizations" / "German.json").write_text(json.dumps({"item_crossbow_moder": "Drachenfrost"}), encoding="utf-8")
            (profile.plugins_dir / "Packs" / "Translations").mkdir(parents=True)
            (profile.plugins_dir / "Packs" / "Translations" / "Packs.English.json").write_text(json.dumps({"Items": {"$vapok_mod_item_backpack_blackforest": "Rugged Backpack"}}), encoding="utf-8")
            texts = modScan.load_localisation(profile)
            self.assertEqual(modScan.display_name("$item_crossbow_moder", texts, "VACrossbowModer"), "Dragonfrost Crossbow")
            self.assertEqual(modScan.display_name("$vapok_mod_item_backpack_blackforest", texts, "BackpackBlackForest"), "Rugged Backpack")
            self.assertEqual(modScan.display_name("Mashed Potato", texts, "pumpkin_soup"), "Mashed Potato")
            self.assertEqual(modScan.display_name("$item_bolt_fire", texts, "VAFireBolt"), "Bolt Fire")
            self.assertEqual(modScan.display_name(None, texts, "odin_hammer"), "Odin Hammer")

    def test_collect_mod_items_reads_every_item_drop(self):
        def game_object(name, shared):
            behaviour = SimpleNamespace(type=SimpleNamespace(name="MonoBehaviour"),
                                        read_typetree=lambda: {"m_itemData": {"m_shared": shared}})
            component = SimpleNamespace(component=SimpleNamespace(deref=lambda: behaviour))
            return SimpleNamespace(type=SimpleNamespace(name="GameObject"), read=lambda: SimpleNamespace(m_Name=name, m_Components=[component]))
        sprite = SimpleNamespace(m_Name="icon")
        objects = [game_object("VACrossbowModer", {"m_name": "$item_crossbow_moder", "m_itemType": 4, "m_maxStackSize": 1, "m_maxQuality": 4, "m_icons": [{"m_PathID": 1}]}),
                   game_object("corn", {"m_name": "$corn", "m_itemType": 2, "m_maxStackSize": 20, "m_icons": []}),
                   SimpleNamespace(type=SimpleNamespace(name="Sprite"), read=lambda: sprite)]
        found = modItems.collect_mod_items(objects, lambda pointer: pointer.deref(), lambda ref, _owner: sprite)
        self.assertEqual(set(found), {"VACrossbowModer", "corn"})
        record = modItems.item_record("VACrossbowModer", found["VACrossbowModer"][0], {"item_crossbow_moder": "Dragonfrost Crossbow"}, ["VACrossbowModer.png"])
        self.assertEqual(record, {"display_name": "Dragonfrost Crossbow", "item_type": "Bow", "max_stack": 1, "max_quality": 4, "variants": 1, "icons": ["VACrossbowModer.png"]})
        self.assertEqual(modItems.embedded_bundle_offsets(b"xxUnityFS\x00yyUnityFS\x00"), [2, 12])

    def test_catalog_round_trip_and_overrides(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = _profile(Path(temp))
            mods = Path(temp) / "workspace" / "mods"
            items = {"VACrossbowModer": {"display_name": "Dragonfrost Crossbow", "item_type": "Bow", "max_stack": 1, "max_quality": 4, "variants": 1, "icons": []}}
            modScan.write_catalog(mods, profile, {2143840399: "Sailing"}, items)
            self.assertEqual(modScan.load_catalog(mods)["skills"], {"2143840399": "Sailing"})
            before = dict(ITEMS_BY_PREFAB)
            try:
                registered = modOverride.apply_overrides(Path(temp) / "workspace")
                self.assertEqual(registered, 1)
                self.assertEqual(resolve_item("VACrossbowModer").display_name, "Dragonfrost Crossbow")
                self.assertEqual(modOverride.skill_label(2143840399), "Sailing")
                self.assertEqual(modOverride.skill_label(-2143840399), "Sailing")
                self.assertEqual(modOverride.skill_label(110), "Ride")
                self.assertEqual(modOverride.skill_label(12345), "Unknown (12345)")
                self.assertEqual(register_items([ItemDefinition(prefab="SwordBronze", display_name="Not replaced")]), 0)
                self.assertEqual(resolve_item("SwordBronze").display_name, "Bronze Sword")
            finally:
                ITEMS_BY_PREFAB.clear()
                ITEMS_BY_PREFAB.update(before)
                modOverride.reset_overrides()
            self.assertEqual(modOverride.apply_overrides(Path(temp) / "empty"), 0)

    def test_scan_profile_without_unitypy_still_records_skills(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = _profile(Path(temp))
            (profile.plugins_dir / "Sailing.dll").write_bytes(b"MZ" + _utf16("Sailing"))
            seen = []
            with patch.object(modItems, "items_available", return_value=False):
                report = modScan.scan_profile(profile, Path(temp) / "mods", lambda stage, done, total: seen.append(stage))
            self.assertEqual((report.dll_count, report.item_count, report.items_available), (1, 0, False))
            self.assertEqual(modScan.load_catalog(Path(temp) / "mods")["skills"]["2143840399"], "Sailing")
            self.assertIn("Reading plugin strings", seen)


class ModProfileTests(unittest.TestCase):
    def test_profiles_are_discovered_from_game_and_managers(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp) / "Valheim"
            (game / "BepInEx" / "plugins").mkdir(parents=True)
            appdata = Path(temp) / "Roaming"
            (appdata / "Thunderstore Mod Manager" / "DataFolder" / "Valheim" / "profiles" / "Hard" / "BepInEx" / "plugins").mkdir(parents=True)
            (appdata / "Thunderstore Mod Manager" / "DataFolder" / "Valheim" / "profiles" / "Empty").mkdir(parents=True)
            (appdata / "r2modmanPlus-local" / "Valheim" / "profiles" / "Alt" / "BepInEx" / "plugins").mkdir(parents=True)
            names = [p.name for p in discover_profiles(game, appdata)]
            self.assertEqual(names, ["Game folder (BepInEx)", "Thunderstore: Hard", "r2modman: Alt"])
            self.assertIsNone(profile_from_directory(appdata))
            self.assertEqual(profile_from_directory(game / "BepInEx").plugins_dir, game / "BepInEx" / "plugins")
            self.assertEqual(discover_profiles(None, Path(temp) / "nowhere"), [])


@unittest.skipUnless(os.environ.get("WULFPACK_LIVE_MODS"), "set WULFPACK_LIVE_MODS=1 to scan the installed mod profiles")
class LiveModScanTests(unittest.TestCase):
    def test_scans_a_real_profile(self):
        profiles = [p for p in discover_profiles() if p.plugin_count() > 20]
        if not profiles:
            self.skipTest("no large mod profile installed")
        with tempfile.TemporaryDirectory() as temp:
            report = modScan.scan_profile(profiles[0], Path(temp))
            catalog = modScan.load_catalog(Path(temp))
            self.assertEqual(catalog["skills"].get("2143840399"), "Sailing")
            self.assertEqual(catalog["skills"].get("924814679"), "midnightsfx.hauling")
            if report.items_available:
                self.assertEqual(catalog["items"]["VACrossbowModer"]["display_name"], "Dragonfrost Crossbow")
                self.assertTrue((Path(temp) / "icons" / "VACrossbowModer.png").is_file())


if __name__ == "__main__":
    unittest.main()
