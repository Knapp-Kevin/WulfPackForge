import logging
import sys
import threading
import unittest
from types import SimpleNamespace

from subscripts.silentErrors import detach_hooks, install_hooks

LOGGER = "subscripts.silentErrors"


def _unraisable_args(exc, obj):
    return SimpleNamespace(exc_type=type(exc), exc_value=exc, exc_traceback=exc.__traceback__,
                           err_msg=None, object=obj)


class SilentErrorTests(unittest.TestCase):
    def tearDown(self):
        detach_hooks()

    def test_unraisable_hook_logs_the_exception_and_object(self):
        install_hooks()
        with self.assertLogs(LOGGER, level=logging.ERROR) as caught:
            sys.unraisablehook(_unraisable_args(ValueError("during __del__"), "the-doomed-object"))
        message = "\n".join(caught.output)
        self.assertIn("ValueError", message)
        self.assertIn("the-doomed-object", message)

    def test_thread_hook_logs_a_worker_failure(self):
        install_hooks()

        def explode():
            raise ZeroDivisionError("worker died")

        with self.assertLogs(LOGGER, level=logging.ERROR) as caught:
            worker = threading.Thread(target=explode, name="wulfpack-scan-0")
            worker.start()
            worker.join()
        message = "\n".join(caught.output)
        self.assertIn("ZeroDivisionError", message)
        self.assertIn("wulfpack-scan-0", message)

    def test_a_worker_exiting_through_system_exit_is_not_reported_as_a_failure(self):
        install_hooks()
        logging.getLogger(LOGGER).error("anchor")  # assertLogs needs at least one record
        with self.assertLogs(LOGGER, level=logging.ERROR) as caught:
            logging.getLogger(LOGGER).error("anchor")
            worker = threading.Thread(target=sys.exit, name="wulfpack-quiet")
            worker.start()
            worker.join()
        self.assertNotIn("wulfpack-quiet", "\n".join(caught.output))

    def test_detach_restores_both_hooks(self):
        before = (sys.unraisablehook, threading.excepthook)
        install_hooks()
        self.assertIsNot(sys.unraisablehook, before[0])
        self.assertIsNot(threading.excepthook, before[1])
        detach_hooks()
        self.assertIs(sys.unraisablehook, before[0])
        self.assertIs(threading.excepthook, before[1])

    def test_installing_twice_still_restores_the_original_hooks(self):
        before = (sys.unraisablehook, threading.excepthook)
        install_hooks()
        install_hooks()
        detach_hooks()
        self.assertIs(sys.unraisablehook, before[0])
        self.assertIs(threading.excepthook, before[1])


if __name__ == "__main__":
    unittest.main()
