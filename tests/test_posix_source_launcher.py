import pathlib
import shutil
import subprocess
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "run-wulfpack-forge.sh"


class PosixSourceLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = LAUNCHER.read_text(encoding="utf-8")

    def test_launcher_is_present_and_uses_its_own_directory(self):
        self.assertTrue(LAUNCHER.is_file())
        self.assertTrue(self.script.startswith("#!/usr/bin/env bash"))
        self.assertIn('cd "$(dirname "$0")"', self.script)
        self.assertNotIn("\r", self.script, "the POSIX launcher must keep LF line endings")

    def test_launcher_uses_a_private_environment(self):
        self.assertIn('VENV_DIR=".wulfpack-forge-venv"', self.script)
        self.assertIn('"$VENV_PYTHON" -m pip install', self.script)
        self.assertIn("-r requirements.txt", self.script)
        self.assertIn('"$VENV_PYTHON" main.py "$@"', self.script)

    def test_launcher_checks_supported_python_versions(self):
        for version in ("3,10", "3,11", "3,12", "3,13", "3,14"):
            self.assertIn(version, self.script)

    def test_launcher_parses_as_bash(self):
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash is not available on this machine")
        result = subprocess.run([bash, "-n", str(LAUNCHER)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
