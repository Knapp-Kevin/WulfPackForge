import unittest

from subscripts.playerDataUtil import (
    SUPPORTED_PLAYER_DATA_VERSIONS,
    pack_player_data_hex,
    payload_is_supported,
    unpack_player_data_hex,
)
from subscripts.saveErrors import SaveFormatError
from tests.fixture_saves import realistic_player_data, realistic_player_hex


class PlayerDataCodecTests(unittest.TestCase):
    def test_round_trip_is_byte_identical(self):
        payload = realistic_player_hex()
        self.assertEqual(pack_player_data_hex(unpack_player_data_hex(payload)), payload)

    def test_unpack_preserves_unknown_and_modded_values(self):
        data = unpack_player_data_hex(realistic_player_hex())
        self.assertEqual([s["id"] for s in data["skills"]], [1, 500])
        self.assertEqual(data["hair"], "HairModded99")
        self.assertEqual(data["model_index"], 2)
        self.assertEqual(len(data["foods"]), 4)
        self.assertEqual(data["inventory"][2]["grid_y"], 7)
        self.assertEqual(data["custom_data"], {"SomeMod.key": "value"})

    def test_hdr_appearance_floats_round_trip_without_normalising(self):
        data = unpack_player_data_hex(realistic_player_hex())
        data["skin_color"] = [2.0, 4.0, 8.0]
        data["hair_color"] = [0.5, 2.5, 10.0]
        reparsed = unpack_player_data_hex(pack_player_data_hex(data))
        self.assertEqual(reparsed["skin_color"], [2.0, 4.0, 8.0])
        self.assertEqual(reparsed["hair_color"], [0.5, 2.5, 10.0])

    def test_trailing_bytes_raise_save_format_error(self):
        payload = realistic_player_hex() + (b"\xde\xad\xbe\xef" * 4).hex()
        with self.assertRaises(SaveFormatError) as ctx:
            unpack_player_data_hex(payload)
        self.assertIn("unconsumed", str(ctx.exception).lower())

    def test_truncated_payload_raises_save_format_error_not_eoferror(self):
        payload = realistic_player_hex()[:-40]
        with self.assertRaises(SaveFormatError):
            unpack_player_data_hex(payload)

    def test_invalid_utf8_string_round_trips_losslessly(self):
        raw = bytearray(bytes.fromhex(realistic_player_hex()))
        index = raw.find(b"Frostwulf")
        raw[index:index + 9] = b"\xff\xfeViking" + b"X"
        payload = bytes(raw).hex()
        self.assertEqual(pack_player_data_hex(unpack_player_data_hex(payload)), payload)

    def test_payload_is_supported_for_known_versions_only(self):
        data = realistic_player_data()
        self.assertIn((29, 106, 2), SUPPORTED_PLAYER_DATA_VERSIONS)
        self.assertTrue(payload_is_supported(data))
        data["version"] = 30
        self.assertFalse(payload_is_supported(data))




class UnreadablePayloadRestatementTests(unittest.TestCase):
    """A payload body this build cannot parse is restated in terms of its version."""

    def _unreadable(self, version: int) -> str:
        """A payload stamped ``version`` whose body this build cannot parse."""
        packed = pack_player_data_hex(realistic_player_data())
        return version.to_bytes(4, "little", signed=True).hex() + packed[8:80]

    def test_an_unreadable_newer_payload_names_its_version_not_a_byte_count(self):
        with self.assertRaises(SaveFormatError) as caught:
            unpack_player_data_hex(self._unreadable(34))
        message = str(caught.exception)
        self.assertIn("34", message)
        self.assertIn("newer Valheim", message)
        self.assertNotIn("wanted", message)
        with self.assertRaises(SaveFormatError) as known:
            unpack_player_data_hex(self._unreadable(33))
        self.assertIn("wanted", str(known.exception), "33 is a layout this build reads, so truncation is corruption")

    def test_a_corrupt_known_version_payload_keeps_its_original_error(self):
        with self.assertRaises(SaveFormatError) as caught:
            unpack_player_data_hex(self._unreadable(29))
        self.assertIn("wanted", str(caught.exception))

    def test_a_newer_payload_that_still_parses_stays_readable(self):
        payload = realistic_player_data()
        payload["version"] = 30
        self.assertEqual(unpack_player_data_hex(pack_player_data_hex(payload))["version"], 30)

    def test_an_empty_payload_still_returns_empty(self):
        self.assertEqual(unpack_player_data_hex(""), {})


class V33PayloadTests(unittest.TestCase):
    """The Valheim 1.0 payload: v33 body, v109 items, string biomes, trailing build-UI blob."""

    def setUp(self):
        from tests.fixture_saves import realistic_v33_player_data
        self.data = realistic_v33_player_data()
        self.packed = pack_player_data_hex(self.data)

    def test_v33_payload_round_trips_byte_identically(self):
        unpacked = unpack_player_data_hex(self.packed)
        self.assertEqual(pack_player_data_hex(unpacked), self.packed)
        self.assertTrue(all("_wire" in item for item in unpacked["inventory"]))
        self.assertTrue(all("_wire" not in item for item in unpack_player_data_hex(pack_player_data_hex(realistic_player_data()))["inventory"]))

    def test_inventory_count_is_ushort_from_inventory_version_108(self):
        def count_offset(data):
            head = 4 + 4 * 4 + 1 + len(data["guardian_power"]) + 4 + 4  # version, four floats, string, cooldown, inv version
            return head
        v33 = bytes.fromhex(self.packed)
        self.assertEqual(int.from_bytes(v33[count_offset(self.data):count_offset(self.data) + 2], "little"), 3)
        v29 = bytes.fromhex(pack_player_data_hex(realistic_player_data()))
        self.assertEqual(int.from_bytes(v29[count_offset(self.data):count_offset(self.data) + 4], "little"), 3)
        self.assertNotEqual(v33[count_offset(self.data) + 2:count_offset(self.data) + 4], b"\x00\x00")

    def test_known_biomes_survive_as_opaque_strings(self):
        self.assertEqual(unpack_player_data_hex(self.packed)["known_biomes"], ["$biome_meadows", "Meadows", "$biome_none"])

    def test_build_ui_blob_round_trips_verbatim(self):
        self.assertEqual(unpack_player_data_hex(self.packed)["build_ui"], bytes(range(74)))
        without = dict(self.data)
        without.pop("build_ui")
        self.assertEqual(unpack_player_data_hex(pack_player_data_hex(without))["build_ui"], b"")

    def test_payload_is_supported_accepts_both_triples(self):
        for triple, expected in (((29, 106, 2), True), ((33, 109, 2), True), ((33, 106, 2), False), ((30, 106, 2), False)):
            version, inventory_version, skill_version = triple
            data = {"version": version, "inventory_version": inventory_version, "skill_version": skill_version}
            self.assertEqual(payload_is_supported(data), expected, triple)


if __name__ == "__main__":
    unittest.main()
