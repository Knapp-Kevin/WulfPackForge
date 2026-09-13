import logging
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from subscripts import crashReports
from subscripts.crashReports import (
    EMPTY_REPORT_CAP,
    REPORT_GLOB,
    acknowledge,
    install,
    previous_reports,
    prune_reports,
    release,
    reports_dir,
)
from subscripts.logSetup import detach_logging

ROOT = Path(__file__).resolve().parents[1]
SUBPROCESS_TIMEOUT = 120  # a faulting child is the likeliest hang in this suite


WORKER = """
import threading
started = threading.Event()
def park():
    started.set()
    threading.Event().wait(30)
threading.Thread(target=park, name="wulfpack-parked", daemon=True).start()
started.wait(5)
"""


def _fault_script(report_dir: Path, with_worker: bool) -> str:
    """A child that arms capture into ``report_dir`` and then genuinely faults.

    Built by concatenation rather than interpolation: a multi-line block substituted into an
    indented template defeats ``textwrap.dedent`` and the child dies on an IndentationError
    before it ever faults, which looks exactly like "capture did not work".
    """
    head = textwrap.dedent(f"""
        import ctypes, sys
        sys.path.insert(0, {str(ROOT)!r})
        from subscripts.crashReports import install
        install({str(report_dir)!r})
    """)
    tail = textwrap.dedent("""
        def faulting_frame():
            ctypes.c_char.from_address(0).value = b"x"
        faulting_frame()
    """)
    return head + (WORKER if with_worker else "") + tail


def _run_fault(report_dir: Path, with_worker: bool = False):
    script = report_dir / "child.py"
    script.write_text(_fault_script(report_dir, with_worker), encoding="utf-8")
    return subprocess.run([sys.executable, str(script)], capture_output=True,
                          text=True, timeout=SUBPROCESS_TIMEOUT)


def _reports(root: Path):
    return sorted(reports_dir(root).glob(REPORT_GLOB))


def _write(path: Path, text: str, age_seconds: float = 0.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


class CrashReportTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.logs = self.root / "logs"

    def tearDown(self):
        release()
        detach_logging()
        self._temp.cleanup()

    # -------------------------------------------------------------- the point
    def test_a_native_fault_writes_a_python_stack_into_the_report(self):
        result = _run_fault(self.root)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        written = [p for p in _reports(self.root) if p.stat().st_size > 0]
        self.assertEqual(len(written), 1, f"expected one report, found {written}")
        text = written[0].read_text(encoding="utf-8", errors="replace")
        # Platform-neutral: Windows says "access violation", POSIX "Segmentation fault".
        self.assertIn("Current thread", text)
        self.assertIn("faulting_frame", text)

    def test_the_report_records_every_thread(self):
        result = _run_fault(self.root, with_worker=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        written = [p for p in _reports(self.root) if p.stat().st_size > 0]
        self.assertEqual(len(written), 1, result.stdout + result.stderr)
        text = written[0].read_text(encoding="utf-8", errors="replace")
        # faulthandler identifies threads by id, not by name, so the worker is proved present
        # by its own stack: a second "Thread 0x" block carrying the frame it was parked in.
        # With all_threads=False only the "Current thread" block is written and both fail.
        self.assertIn("Thread 0x", text.replace("Current thread 0x", ""))
        self.assertIn("in park", text)

    # -------------------------------------------------------------- placement
    def test_the_report_follows_the_log_location(self):
        elsewhere = self.root / "somewhere-else"
        with patch.object(crashReports, "log_path", return_value=elsewhere / "wulfpack-forge.log"):
            self.assertEqual(reports_dir(), elsewhere)
            path = install()
        self.assertIsNotNone(path)
        self.assertEqual(path.parent, elsewhere)

    def test_the_report_name_uses_the_windows_safe_stamp(self):
        path = install(self.root)
        self.assertIsNotNone(path)
        self.assertNotIn(":", path.name)
        self.assertRegex(path.name, r"^crash-\d{8}T\d{6}Z-\d+(-\d+)?\.log$")

    @unittest.skipIf(os.name == "nt", "POSIX file modes only")
    def test_the_report_is_not_world_readable_on_posix(self):
        path = install(self.root)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_install_never_overwrites_an_existing_report(self):
        self.logs.mkdir(parents=True)
        with patch.object(crashReports, "_report_name", return_value="crash-20260908T151056Z-4242.log"):
            sentinel = _write(self.logs / "crash-20260908T151056Z-4242.log", "PRECIOUS CRASH DATA")
            path = install(self.root)
        self.assertNotEqual(path, sentinel)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "PRECIOUS CRASH DATA")

    def test_install_returns_none_and_logs_when_the_directory_is_unusable(self):
        _write(self.logs, "not a directory")
        with self.assertLogs("subscripts.crashReports", level=logging.ERROR) as caught:
            self.assertIsNone(install(self.root))
        self.assertIn("NOT armed", "\n".join(caught.output))

    # -------------------------------------------------------------- release
    def test_clean_release_removes_the_empty_report(self):
        path = install(self.root)
        self.assertTrue(path.exists())
        self.assertIsNone(release())
        self.assertFalse(path.exists())
        self.assertEqual(_reports(self.root), [])

    def test_release_keeps_a_report_that_has_content(self):
        path = install(self.root)
        crashReports._handle.write(b"Current thread 0x0000\n")
        self.assertEqual(release(), path)
        self.assertIn("Current thread", path.read_text(encoding="utf-8"))

    def test_release_is_safe_when_capture_was_never_armed(self):
        self.assertIsNone(release())

    def test_release_is_safe_when_the_report_vanished(self):
        install(self.root)
        # Windows refuses to unlink a file that is still open, so the disappearance is
        # simulated at the stat() call release() actually makes.
        with patch.object(Path, "stat", side_effect=FileNotFoundError("gone")):
            self.assertIsNone(release())

    # -------------------------------------------------------------- reading
    def test_previous_reports_returns_non_empty_reports_newest_first_by_mtime(self):
        old = _write(self.logs / "crash-20260908T090000Z-1.log", "x", age_seconds=300)
        new = _write(self.logs / "crash-20260908T080000Z-2.log", "x", age_seconds=10)
        middle = _write(self.logs / "crash-20260908T100000Z-3.log", "x", age_seconds=100)
        self.assertEqual(previous_reports(self.root), [new, middle, old])

    def test_previous_reports_ignores_empty_reports_and_the_current_run(self):
        real = _write(self.logs / "crash-20260908T090000Z-1.log", "x")
        _write(self.logs / "crash-20260908T090000Z-2.log", "")
        mine = install(self.root)
        self.assertEqual(previous_reports(self.root), [real])
        self.assertNotIn(mine, previous_reports(self.root))

    def test_previous_reports_survives_a_polluted_directory(self):
        real = _write(self.logs / "crash-20260908T090000Z-1.log", "x")
        _write(self.logs / "crash-notes.log", "a stray file a user dropped here")
        (self.logs / "crash-directory.log").mkdir()
        self.assertIn(real, previous_reports(self.root))

    def test_previous_reports_returns_empty_when_the_directory_is_missing(self):
        self.assertEqual(previous_reports(self.root), [])

    def test_previous_reports_returns_empty_when_the_directory_cannot_be_read(self):
        _write(self.logs / "crash-20260908T090000Z-1.log", "x")
        with patch.object(Path, "glob", side_effect=OSError("permission denied")):
            self.assertEqual(previous_reports(self.root), [])

    # -------------------------------------------------------------- acknowledging
    def test_acknowledge_renames_the_report_and_hides_it_from_previous_reports(self):
        report = _write(self.logs / "crash-20260909T023025Z-1.log", "x")
        self.assertEqual(previous_reports(self.root), [report])
        seen = acknowledge(report)
        self.assertEqual(seen, self.logs / "crash-20260909T023025Z-1.seen.log")
        self.assertFalse(report.exists())
        self.assertTrue(seen.is_file())
        self.assertEqual(previous_reports(self.root), [])

    def test_acknowledge_is_safe_twice_and_on_a_missing_file(self):
        report = _write(self.logs / "crash-20260909T023025Z-1.log", "x")
        seen = acknowledge(report)
        self.assertIsNone(acknowledge(seen))
        self.assertTrue(seen.is_file())
        self.assertIsNone(acknowledge(self.logs / "crash-20260909T023025Z-9.log"))

    def test_prune_counts_acknowledged_reports_toward_retention(self):
        oldest = _write(self.logs / "crash-20260901T000000Z-1.log", "x", age_seconds=600)
        for index in range(2, 7):
            path = _write(self.logs / f"crash-20260901T00000{index}Z-{index}.log", "x", age_seconds=600 - index * 60)
            if index >= 4:
                acknowledge(path)
        removed = prune_reports(self.root, keep=5)
        self.assertEqual(removed, [oldest])
        self.assertEqual(len(_reports(self.root)), 5)

    # -------------------------------------------------------------- pruning
    def test_prune_removes_over_retention_non_empty_reports(self):
        made = [_write(self.logs / f"crash-20260908T09000{i}Z-{i}.log", "x", age_seconds=100 - i)
                for i in range(7)]
        removed = prune_reports(self.root, keep=5)
        survivors = [p for p in made if p.exists()]
        self.assertEqual(len(survivors), 5)
        self.assertEqual(sorted(removed), sorted(p for p in made if not p.exists()))

    def test_prune_removes_only_empty_reports_that_are_both_old_and_over_the_cap(self):
        old_empty = [_write(self.logs / f"crash-20260908T08000{i}Z-{i}.log", "", age_seconds=172800)
                     for i in range(EMPTY_REPORT_CAP + 2)]
        prune_reports(self.root)
        self.assertEqual(len([p for p in old_empty if p.exists()]), EMPTY_REPORT_CAP)

    def test_prune_keeps_a_recent_empty_report(self):
        recent = _write(self.logs / "crash-20260908T090000Z-99.log", "", age_seconds=60)
        for i in range(EMPTY_REPORT_CAP + 2):
            _write(self.logs / f"crash-20260908T08000{i}Z-{i}.log", "", age_seconds=172800)
        prune_reports(self.root)
        self.assertTrue(recent.exists(), "a concurrent instance's in-progress report was deleted")

    def test_prune_keeps_an_old_empty_report_within_the_cap(self):
        old = _write(self.logs / "crash-20260908T080000Z-1.log", "", age_seconds=172800)
        prune_reports(self.root)
        self.assertTrue(old.exists(), "age alone must not be enough to prune")

    def test_prune_reports_an_unlinkable_file_without_raising(self):
        made = [_write(self.logs / f"crash-20260908T09000{i}Z-{i}.log", "x", age_seconds=100 - i)
                for i in range(7)]
        with patch.object(Path, "unlink", side_effect=OSError("file is open")):
            self.assertEqual(prune_reports(self.root, keep=5), [])
        self.assertTrue(all(p.exists() for p in made))


if __name__ == "__main__":
    unittest.main()
