import logging
import tempfile
import unittest
from pathlib import Path

from subscripts.logSetup import HANDLER_NAME, configure_logging, detach_logging


class LogSetupTests(unittest.TestCase):
    def tearDown(self):
        detach_logging()

    def test_records_reach_the_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = configure_logging(Path(temp))
            self.assertEqual(path, Path(temp) / "logs" / "wulfpack-forge.log")
            logging.getLogger("ui.mainWindow").error("Could not open character %s", "broken.fch")
            for handler in logging.getLogger().handlers:
                handler.flush()
            text = path.read_text(encoding="utf-8")
            self.assertIn("broken.fch", text)
            self.assertIn("ERROR", text)
            self.assertIn("ui.mainWindow", text)
            detach_logging()  # release the file before the temporary directory is removed

    def test_configuring_twice_keeps_one_handler(self):
        with tempfile.TemporaryDirectory() as temp:
            first = configure_logging(Path(temp))
            second = configure_logging(Path(temp))
            self.assertEqual(first, second)
            ours = [h for h in logging.getLogger().handlers if h.get_name() == HANDLER_NAME]
            self.assertEqual(len(ours), 1)
            detach_logging()

    def test_unwritable_root_returns_none_without_raising(self):
        with tempfile.TemporaryDirectory() as temp:
            blocker = Path(temp) / "logs"
            blocker.write_text("not a directory", encoding="utf-8")
            self.assertIsNone(configure_logging(Path(temp)))


if __name__ == "__main__":
    unittest.main()
