import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from subscripts import iconExtraction as ie


class _Sprite:
    def __init__(self, name, colour=(255, 0, 0, 255)):
        self.m_Name = name
        self.image = _Image(colour)


class _Image:
    def __init__(self, colour):
        self.colour = colour

    def save(self, path):
        from PySide6.QtGui import QImage, QColor
        image = QImage(4, 4, QImage.Format_ARGB32)
        image.fill(QColor(*self.colour))
        assert image.save(str(path))


def _game_object(name, components):
    return SimpleNamespace(type=SimpleNamespace(name="GameObject"),
                           read=lambda: SimpleNamespace(m_Name=name, m_Components=components))


def _item_drop(icons):
    behaviour = SimpleNamespace(type=SimpleNamespace(name="MonoBehaviour"),
                                read_typetree=lambda: {"m_itemData": {"m_shared": {"m_icons": icons}}})
    return SimpleNamespace(component=SimpleNamespace(deref=lambda: behaviour))


def _plain_component():
    behaviour = SimpleNamespace(type=SimpleNamespace(name="MonoBehaviour"), read_typetree=lambda: {"m_other": 1})
    return SimpleNamespace(component=SimpleNamespace(deref=lambda: behaviour))


class CollectItemIconsTests(unittest.TestCase):
    def test_follows_prefab_to_item_drop_to_icons(self):
        sprites = {1: _Sprite("SwordBronze"), 2: _Sprite("shield0"), 3: _Sprite("shield1")}
        objects = [
            _game_object("SwordBronze", [_plain_component(), _item_drop([{"m_PathID": 1}])]),
            _game_object("ShieldBanded", [_item_drop([{"m_PathID": 2}, {"m_PathID": 3}])]),
            _game_object("Tree", [_plain_component()]),
            _game_object("NotWanted", [_item_drop([{"m_PathID": 1}])]),
            SimpleNamespace(type=SimpleNamespace(name="Texture2D"), read=lambda: None),
        ]
        found = ie.collect_item_icons(objects, {"SwordBronze", "ShieldBanded", "Tree"},
                                      lambda pointer: pointer.deref(), lambda ref, _owner: sprites.get(ref["m_PathID"]))
        self.assertEqual({k: [s.m_Name for s in v] for k, v in found.items()},
                         {"SwordBronze": ["SwordBronze"], "ShieldBanded": ["shield0", "shield1"]})

    def test_save_sprites_writes_base_and_variant_files_and_reports_progress(self):
        found = {"ShieldBanded": [_Sprite("a"), _Sprite("b")], "SwordBronze": [_Sprite("c")]}
        seen = []
        with tempfile.TemporaryDirectory() as temp:
            written = ie.save_sprites(found, Path(temp), lambda stage, done, total: seen.append((done, total)))
            self.assertEqual(written, {"ShieldBanded": ["ShieldBanded.png", "ShieldBanded_1.png"], "SwordBronze": ["SwordBronze.png"]})
            self.assertEqual(ie.cached_icon_path(Path(temp), "ShieldBanded", 1).name, "ShieldBanded_1.png")
            self.assertEqual(ie.cached_icon_path(Path(temp), "ShieldBanded", 5).name, "ShieldBanded.png")
            self.assertIsNone(ie.cached_icon_path(Path(temp), "Missing"))
        self.assertEqual(seen, [(1, 2), (2, 2)])

    def test_game_directory_detection_and_index(self):
        with tempfile.TemporaryDirectory() as temp:
            steam = Path(temp) / "steam"
            self.assertIsNone(ie.find_game_directory(steam))
            self.assertIsNone(ie.find_game_directory(None))
            game = steam / "steamapps" / "common" / "Valheim"
            (game / ie.BUNDLES_RELATIVE).mkdir(parents=True)
            self.assertEqual(ie.find_game_directory(steam), game)
            self.assertEqual(ie.load_index(Path(temp)), {})
            (Path(temp) / ie.INDEX_NAME).write_text("not json", encoding="utf-8")
            self.assertEqual(ie.load_index(Path(temp)), {})
            (Path(temp) / ie.INDEX_NAME).write_text(json.dumps({"icons": {"a": ["a.png"]}}), encoding="utf-8")
            self.assertEqual(ie.load_index(Path(temp))["icons"], {"a": ["a.png"]})

    def test_availability_follows_the_optional_import(self):
        with patch.object(ie.importlib.util, "find_spec", return_value=None):
            self.assertFalse(ie.extraction_available())
        with patch.object(ie.importlib.util, "find_spec", return_value=object()):
            self.assertTrue(ie.extraction_available())


@unittest.skipUnless(os.environ.get("WULFPACK_LIVE_GAME"), "set WULFPACK_LIVE_GAME=1 to extract from the installed game")
class LiveGameExtractionTests(unittest.TestCase):
    def test_extracts_real_icons_from_the_installed_game(self):
        from subscripts.characterDiscovery import registry_steam_path
        game = ie.find_game_directory(registry_steam_path())
        if game is None or not ie.extraction_available():
            self.skipTest("no installed game or UnityPy")
        with tempfile.TemporaryDirectory() as temp:
            report = ie.extract_icons(game, ["SwordBronze", "ShieldBanded", "ArmorDress4", "Beard1"], Path(temp))
            self.assertEqual(report.extracted, 3)
            self.assertEqual(report.missing, ["Beard1"])
            self.assertTrue((Path(temp) / "SwordBronze.png").is_file())
            self.assertTrue((Path(temp) / "ShieldBanded_1.png").is_file())
            self.assertEqual(ie.load_index(Path(temp))["icons"]["SwordBronze"], ["SwordBronze.png"])


if __name__ == "__main__":
    unittest.main()
