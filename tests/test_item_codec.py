"""The version 109 item record: flags recomputed from values, hashed identity, wire-block contract."""
import unittest

from data.itemHashes import hash_index
from data.items import ITEMS_BY_PREFAB
from subscripts.binaryIO import BinaryReader, BinaryWriter
from subscripts.itemCodec import ITEM_UNKNOWN_PREFIX, read_item, resolve_prefab_hash, write_item
from subscripts.playerDataUtil import new_inventory_item
from subscripts.stableHash import stable_hash_code
from tests.fixture_saves import realistic_player_data

V109 = 109


def encode(item: dict, version: int = V109) -> bytes:
    writer = BinaryWriter()
    write_item(writer, item, version)
    return writer.get_bytes()


def decode(payload: bytes, version: int = V109) -> dict:
    reader = BinaryReader(payload)
    item = read_item(reader, version)
    reader.require_exhausted("item")
    return item


def full_record() -> bytes:
    """Every flag set, hand-built in the game's order."""
    writer = BinaryWriter()
    writer.write_int32(13773)                      # durability 137.73
    writer.write_byte(7); writer.write_byte(3); writer.write_byte(1)
    writer.write_byte(0xFF)                        # all eight flags
    writer.write_ushort(3); writer.write_ushort(62); writer.write_int32(2)
    writer.write_long(76561198000000000); writer.write_string("Frostwulf")
    writer.write_int32(stable_hash_code("Wood"))
    writer.write_byte(1); writer.write_string("EpicLoot"); writer.write_string("{}")
    writer.write_byte(1)                           # cheated
    return writer.get_bytes()


class V109RecordTests(unittest.TestCase):
    def test_a_v109_record_round_trips_byte_identically(self):
        raw = full_record()
        item = decode(raw)
        self.assertEqual((item["prefab"], item["quality"], item["stack"], item["variant"]), ("Wood", 3, 62, 2))
        self.assertEqual((item["grid_x"], item["grid_y"], item["world_level"]), (7, 3, 1))
        self.assertEqual((item["picked_up"], item["equipped"], item["crafter_name"]), (True, True, "Frostwulf"))
        self.assertEqual(item["custom_data"], {"EpicLoot": "{}"})
        self.assertAlmostEqual(item["durability"], 137.73)
        self.assertEqual(item["_wire"], {"prefab_hash": stable_hash_code("Wood"), "durability_raw": 13773, "cheat_flags": 1})
        self.assertEqual(encode(item), raw)

    def test_item_flags_are_recomputed_from_values(self):
        base = new_inventory_item("Wood", 0, 0, 100.0)
        base["picked_up"] = False
        plain = encode(base)
        self.assertEqual(plain[7], 64, "only the prefab flag is set for quality 1, stack 1")
        base["quality"] = 3
        self.assertEqual(encode(base)[7], 64 | 4)
        self.assertEqual(len(encode(base)), len(plain) + 2, "a present quality adds one ushort")

    def test_absent_quality_and_stack_read_as_one(self):
        writer = BinaryWriter()
        writer.write_int32(100); writer.write_byte(0); writer.write_byte(0); writer.write_byte(0)
        writer.write_byte(0); writer.write_byte(0)  # no flags, clean cheat byte
        item = decode(writer.get_bytes())
        self.assertEqual((item["quality"], item["stack"]), (1, 1))

    def test_unedited_durability_reuses_the_stored_raw_value(self):
        item = decode(full_record())
        self.assertEqual(encode(item)[:4], (13773).to_bytes(4, "little", signed=True))
        item["durability"] = 50.0
        self.assertEqual(encode(item)[:4], (5000).to_bytes(4, "little", signed=True))

    def test_a_cheat_byte_with_unknown_bits_round_trips_verbatim(self):
        raw = full_record()[:-1] + bytes([6])
        item = decode(raw)
        self.assertEqual(item["_wire"]["cheat_flags"], 6)
        self.assertEqual(encode(item), raw)

    def test_a_legacy_record_reads_and_writes_as_before(self):
        legacy = realistic_player_data()["inventory"][0]
        raw = encode(legacy, 106)
        restored = decode(raw, 106)
        self.assertNotIn("_wire", restored)
        self.assertEqual(encode(restored, 106), raw)
        durability = restored.pop("durability")
        expected = dict(legacy)
        self.assertAlmostEqual(durability, expected.pop("durability"), places=3)
        self.assertEqual(restored, expected)


class IdentityTests(unittest.TestCase):
    def test_hash_resolution_uses_the_real_case_prefab(self):
        self.assertEqual(resolve_prefab_hash(stable_hash_code("Wood")), "Wood")
        from_keys = {stable_hash_code(key): key for key in ITEMS_BY_PREFAB}
        self.assertIsNone(from_keys.get(stable_hash_code("Wood")), "the lowercased keys must not resolve")

    def test_every_catalogue_prefab_resolves_uniquely(self):
        prefabs = {definition.prefab for definition in ITEMS_BY_PREFAB.values()}
        self.assertEqual(len(hash_index(stable_hash_code)), len(prefabs))

    def test_an_unresolved_hash_gets_a_stable_non_empty_identity(self):
        unknown = stable_hash_code("ZzNotInAnyCatalogue")
        token = resolve_prefab_hash(unknown)
        self.assertTrue(token.startswith(ITEM_UNKNOWN_PREFIX))
        self.assertEqual(token, resolve_prefab_hash(unknown))
        self.assertGreater(len(token), len(ITEM_UNKNOWN_PREFIX))

    def test_an_unresolved_item_round_trips_to_the_same_bytes(self):
        unknown = stable_hash_code("ZzNotInAnyCatalogue")
        raw = full_record().replace(
            stable_hash_code("Wood").to_bytes(4, "little", signed=True), unknown.to_bytes(4, "little", signed=True))
        item = decode(raw)
        self.assertEqual(item["prefab"], f"{ITEM_UNKNOWN_PREFIX}{unknown}")
        self.assertEqual(encode(item), raw)
        self.assertNotEqual(stable_hash_code(item["prefab"]), unknown, "the token itself is never hashed")

    def test_a_renamed_item_is_written_under_its_new_hash(self):
        item = decode(full_record())
        item["prefab"] = "SwordBronze"
        restored = decode(encode(item))
        self.assertEqual(restored["prefab"], "SwordBronze")
        self.assertEqual(restored["_wire"]["prefab_hash"], stable_hash_code("SwordBronze"))

    def test_an_item_without_a_wire_block_writes_as_a_fresh_clean_item(self):
        from subscripts.newCharacter import STARTING_INVENTORY, _starting_item

        for shape in (new_inventory_item("Torch", 1, 2, 20.0), _starting_item(STARTING_INVENTORY[0])):
            self.assertNotIn("_wire", shape)
            restored = decode(encode(shape))
            self.assertEqual(restored["prefab"], "Torch")
            self.assertEqual(restored["_wire"], {"prefab_hash": stable_hash_code("Torch"), "durability_raw": 2000, "cheat_flags": 0})
            self.assertTrue(encode(shape)[7] & 64)


if __name__ == "__main__":
    unittest.main()
