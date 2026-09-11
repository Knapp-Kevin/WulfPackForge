"""Byte-exact round trip of every Valheim 1.0 character on this machine.

Read-only: each file is read into memory with ``read_bytes`` and nothing under the
characters directory is ever opened for writing, no window, workspace or backup is
involved. Skips by name when no local v46 save exists, so CI (which has none) never
reports a green result it did not earn.
"""
import struct
import unittest
from pathlib import Path

from subscripts.characterDiscovery import candidate_character_directories
from subscripts.fchUtil import parse_save, serialize_save
from subscripts.playerDataUtil import pack_player_data_hex, payload_is_supported, unpack_player_data_hex

V46 = 46


def _local_v46_saves() -> list:
    found = []
    for directory, _source in candidate_character_directories():
        for path in sorted(Path(directory).glob("*.fch")):
            raw = path.read_bytes()
            if len(raw) >= 8 and struct.unpack_from("<i", raw, 4)[0] == V46:
                found.append((path.stem, raw))
    return found


class RealSaveRoundTripTests(unittest.TestCase):
    def test_every_local_v46_character_round_trips_byte_identically(self):
        saves = _local_v46_saves()
        if not saves:
            self.skipTest("no local Valheim 1.0 (v46) character save on this machine")
        checked = []
        for name, raw in saves:
            with self.subTest(character=name):
                root = parse_save(raw)
                self.assertEqual(serialize_save(root), raw, f"{name}: container differs")
                payload = unpack_player_data_hex(root["player_data_hex"])
                self.assertTrue(payload_is_supported(payload), f"{name}: payload triple not supported")
                self.assertEqual(pack_player_data_hex(payload), root["player_data_hex"], f"{name}: payload differs")
                checked.append(name)
        print(f"real v46 saves round-tripped byte-identically: {', '.join(checked)}")


if __name__ == "__main__":
    unittest.main()
