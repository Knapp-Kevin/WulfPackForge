import pathlib
import re
import subprocess
import sys
import unittest

from ui.branding import APP_VERSION, APP_WINDOW_TITLE

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-rc\.\d+)?$")


class ReleaseMarkerTests(unittest.TestCase):
    def test_version_is_well_formed_and_shown(self):
        self.assertRegex(APP_VERSION, VERSION_PATTERN)
        self.assertIn(APP_VERSION, APP_WINDOW_TITLE)

    def test_version_flag_prints_the_version(self):
        result = subprocess.run([sys.executable, str(ROOT / "main.py"), "--version"], capture_output=True, text=True, cwd=ROOT, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), APP_VERSION)

    def test_release_step_drafts_pre_release_tags(self):
        workflow = (ROOT / ".github" / "workflows" / "package-windows.yml").read_text(encoding="utf-8")
        release_step = workflow[workflow.index("Publish GitHub Release"):]
        self.assertIn("--prerelease", release_step)
        self.assertIn("--draft", release_step)
        self.assertIn('-like "*-*"', release_step)


if __name__ == "__main__":
    unittest.main()
