import unittest

from ui.messages import saved_ok


class SavedMessageTests(unittest.TestCase):
    def test_saved_ok_is_one_sentence_without_paths(self):
        text = saved_ok("C:/saves/hero.fch", "C:/ws/backups/hero.fch.20260912.bak")
        self.assertIn("hero.fch", text)
        self.assertIn("backup", text.lower())
        self.assertNotIn("/", text)
        self.assertNotIn("\\", text)
        self.assertNotIn("\n", text)
        self.assertNotIn("backup", saved_ok("C:/saves/hero.fch", None).lower())


if __name__ == "__main__":
    unittest.main()
