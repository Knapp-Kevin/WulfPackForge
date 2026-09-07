import os
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from subscripts.characterRecords import CharacterRecord, CharacterState
from ui.characterPicker import CharacterPickerBar, SCANNING_LABEL


APP = QApplication.instance() or QApplication([])


def fake_record(name="Ares"):
    state = CharacterState(path=f"C:/saves/{name.lower()}.fch", kind="active", source="Local", name=name, player_id=1,
                           date_created=1, modified_at=1_700_000_000.0, size=10, version=43, valid=True)
    return CharacterRecord(key="1:1", name=name, states=[state])


class DiscoveryWorkerTests(unittest.TestCase):
    def test_scan_runs_off_the_ui_thread(self):
        seen = {}

        def discover():
            seen["thread"] = threading.get_ident()
            time.sleep(0.2)
            return [fake_record()]

        picker = CharacterPickerBar(discover=discover)
        picker.refresh(None)
        self.assertEqual(picker.character_combo.itemText(0), SCANNING_LABEL)
        self.assertFalse(picker.btn_open_discovered.isEnabled())
        picker.wait_for_scan()
        self.assertNotEqual(seen["thread"], threading.get_ident())
        self.assertTrue(picker.character_combo.itemText(0).startswith("Ares"))
        self.assertTrue(picker.btn_open_discovered.isEnabled())

    def test_refresh_during_a_scan_runs_once_more(self):
        calls = []

        def discover():
            calls.append(1)
            time.sleep(0.15)
            return [fake_record()]

        picker = CharacterPickerBar(discover=discover)
        picker.refresh(None)
        picker.refresh(None)
        picker.refresh(None)
        picker.wait_for_scan()
        self.assertEqual(len(calls), 2)

    def test_failed_scan_shows_the_empty_state_and_logs(self):
        def discover():
            raise RuntimeError("disk on fire")

        picker = CharacterPickerBar(discover=discover)
        with self.assertLogs("ui.characterPicker", level="ERROR") as logs:
            picker.refresh(None)
            picker.wait_for_scan()
        self.assertTrue(picker.discovery_help.isVisibleTo(picker))
        self.assertTrue(any("disk on fire" in line for line in logs.output))


if __name__ == "__main__":
    unittest.main()
