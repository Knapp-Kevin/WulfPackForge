"""Byte-exact round trip of every readable Valheim character on this machine.

Read-only: each file is read into memory with ``read_bytes`` and nothing under the
characters directory is ever opened for writing, no window, workspace or backup is
involved. Skips by name when no local save exists, so CI (which has none) never reports a
green result it did not earn. A local save newer than this build reads fails the second
test: that is the signal that Valheim has moved its format again.
"""
import struct
import unittest
from pathlib import Path

from subscripts.characterDiscovery import candidate_character_directories
from subscripts.fchUtil import MAX_CHARACTER_SAVE_VERSION, READABLE_CHARACTER_SAVE_VERSIONS, parse_save, serialize_save
from subscripts.playerDataUtil import pack_player_data_hex, payload_is_supported, unpack_player_data_hex


def _local_saves() -> list:
    """(name, container version, bytes) for every local ``*.fch`` with a version header."""
    found = []
    for directory, _source in candidate_character_directories():
        for path in sorted(Path(directory).glob("*.fch")):
            raw = path.read_bytes()
            if len(raw) >= 8:
                found.append((path.stem, struct.unpack_from("<i", raw, 4)[0], raw))
    return found


class RealSaveRoundTripTests(unittest.TestCase):
    def test_every_readable_local_save_round_trips_byte_identically(self):
        saves = [entry for entry in _local_saves() if entry[1] in READABLE_CHARACTER_SAVE_VERSIONS]
        if not saves:
            self.skipTest("no readable local Valheim character save on this machine")
        seen, skipped = {}, []
        for name, version, raw in saves:
            root = parse_save(raw)
            payload = unpack_player_data_hex(root["player_data_hex"])
            if not payload_is_supported(payload):
                skipped.append(f"{name} (container {version}, payload {payload.get('version')})")
                continue
            with self.subTest(character=name):
                self.assertEqual(serialize_save(root), raw, f"{name}: container differs")
                self.assertEqual(pack_player_data_hex(payload), root["player_data_hex"], f"{name}: payload differs")
                seen.setdefault(version, []).append(name)
        print("real saves round-tripped byte-identically, by container version: "
              + "; ".join(f"{version}: {', '.join(names)}" for version, names in sorted(seen.items())))
        print("skipped as read-only (payload layout not supported): " + (", ".join(skipped) or "none"))

    def test_no_local_save_is_newer_than_this_build_reads(self):
        saves = _local_saves()
        if not saves:
            self.skipTest("no local Valheim character save on this machine")
        newer = [(name, version) for name, version, _raw in saves if version > MAX_CHARACTER_SAVE_VERSION]
        self.assertEqual(newer, [], "Valheim has written a save format newer than this build reads")


if __name__ == "__main__":
    unittest.main()
