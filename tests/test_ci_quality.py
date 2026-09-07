import io
import pathlib
import subprocess
import sys
import unittest
from contextlib import redirect_stdout

from subscripts import fchUtil

ROOT = pathlib.Path(__file__).resolve().parents[1]


class CiQualityTests(unittest.TestCase):
    def test_pyflakes_is_clean(self):
        result = subprocess.run([sys.executable, "-m", "pyflakes", "main.py", "data", "subscripts", "ui", "tools", "tests"],
                                capture_output=True, text=True, cwd=ROOT, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_cli_unknown_mode_logs_and_fails(self):
        with self.assertLogs("subscripts.fchUtil", level="ERROR") as logs, redirect_stdout(io.StringIO()) as out:
            code = fchUtil._main(["fchUtil.py", "explode", "a", "b"])
        self.assertEqual(code, 1)
        self.assertTrue(any("explode" in line for line in logs.output))
        self.assertEqual(out.getvalue(), "")

    def test_cli_usage_is_printed_for_missing_arguments(self):
        with redirect_stdout(io.StringIO()) as out:
            code = fchUtil._main(["fchUtil.py"])
        self.assertEqual(code, 1)
        self.assertIn("unpack", out.getvalue())
        self.assertIn("pack", out.getvalue())

    def test_workflow_lints_and_enforces_the_coverage_floor(self):
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.assertIn("python -m pyflakes main.py data subscripts ui tools tests", workflow)
        self.assertIn("--fail-under=85", workflow)
        self.assertIn("requirements-dev.txt", workflow)


if __name__ == "__main__":
    unittest.main()
