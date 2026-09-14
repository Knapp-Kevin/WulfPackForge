import json
import tempfile
import unittest
from pathlib import Path

from subscripts.editorMode import MODE_FULL, MODE_VANILLA, capitalised_words, load_mode, save_mode, settings_path


class EditorModeTests(unittest.TestCase):
    def test_mode_defaults_to_full_and_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(load_mode(root), MODE_FULL)
            save_mode(root, MODE_VANILLA)
            self.assertEqual(load_mode(root), MODE_VANILLA)
            self.assertEqual(json.loads(settings_path(root).read_text(encoding="utf-8"))["schema_version"], 1)
            settings_path(root).write_text("{not json", encoding="utf-8")
            self.assertEqual(load_mode(root), MODE_FULL)
            settings_path(root).write_text(json.dumps({"schema_version": 1, "mode": "other"}), encoding="utf-8")
            self.assertEqual(load_mode(root), MODE_FULL)
            with self.assertRaises(ValueError):
                save_mode(root, "other")

    def test_capitalised_words_rule(self):
        for name in ("Frostwulf", "Frost Wulf", "Sigrun The Bold"):
            self.assertTrue(capitalised_words(name), name)
        for name in ("frostwulf", "Frost wulf", "frost Wulf", "", "   "):
            self.assertFalse(capitalised_words(name), name)


if __name__ == "__main__":
    unittest.main()
