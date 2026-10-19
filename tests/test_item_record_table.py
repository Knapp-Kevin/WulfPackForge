"""ItemData::Save as data (subscripts/itemRecordTable.py): every row behaves as the IL states."""
import unittest

from subscripts.binaryIO import BinaryReader, BinaryWriter
from subscripts.itemCodec import read_item, write_item
from subscripts.itemRecordTable import FLAG_RULES, WRITE_ORDER, encode
from tests.fixture_saves import realistic_v33_player_data, realistic_v34_player_data

FLAG_BYTE = 7  # int32 durability, then grid x, grid y and world level bytes


def quiet_fields(**changes) -> dict:
    """Field values for which no flag predicate holds."""
    fields = {"durability_raw": 1000, "grid_x": 2, "grid_y": 3, "world_level": 0, "picked_up": False,
              "equipped": False, "quality": 1, "stack": 1, "variant": 0, "crafter_id": 0, "crafter_name": "",
              "has_prefab": False, "prefab_hash": 0, "custom_data": {}, "cheated": False}
    fields.update(changes)
    return fields


TRIGGERS = {"picked_up": True, "equipped": True, "quality": 3, "stack": 7, "variant": 2, "crafter_id": 99,
            "has_prefab": True, "custom_data": {"k": "v"}}


def fields_of(item: dict) -> dict:
    wire = item["_wire"]
    return quiet_fields(durability_raw=wire["durability_raw"], grid_x=item["grid_x"], grid_y=item["grid_y"],
                        world_level=item["world_level"], picked_up=item["picked_up"], equipped=item["equipped"],
                        quality=item["quality"], stack=item["stack"], variant=item["variant"],
                        crafter_id=item["crafter_id"], crafter_name=item["crafter_name"],
                        has_prefab=wire["prefab_hash"] != 0, prefab_hash=wire["prefab_hash"],
                        custom_data=item["custom_data"], cheated=bool(wire["cheat_flags"] & 1))


class FlagRuleTests(unittest.TestCase):
    def test_every_flag_rule_sets_exactly_its_bit(self):
        self.assertEqual(encode(quiet_fields())[FLAG_BYTE], 0)
        for bit, field, _predicate, _offset in FLAG_RULES:
            with self.subTest(field=field):
                self.assertEqual(encode(quiet_fields(**{field: TRIGGERS[field]}))[FLAG_BYTE], bit)

    def test_the_crafter_bit_follows_the_id_alone(self):
        self.assertEqual(encode(quiet_fields(crafter_name="Hodr")), encode(quiet_fields()))


class WriteOrderTests(unittest.TestCase):
    def test_every_gated_field_is_written_only_under_its_flag(self):
        base = len(encode(quiet_fields()))
        gated = {field: gate for field, _encoding, gate, _offset in WRITE_ORDER if gate}
        widths = {"quality": 2, "stack": 2, "variant": 4, "crafter_id": 8 + 1, "has_prefab": 4, "custom_data": 1 + 2 + 2}
        for field, width in widths.items():
            with self.subTest(field=field):
                self.assertEqual(len(encode(quiet_fields(**{field: TRIGGERS[field]}))) - base, width)
        self.assertEqual(gated["crafter_name"], gated["crafter_id"])

    def test_narrowed_fields_keep_their_low_bits(self):
        record = encode(quiet_fields(grid_x=257, world_level=258, quality=70000))
        self.assertEqual((record[4], record[6]), (1, 2))
        self.assertEqual(int.from_bytes(record[8:10], "little"), 70000 & 0xFFFF)

    def test_the_cheated_byte_is_bit_zero_only(self):
        self.assertEqual(encode(quiet_fields(cheated=True))[-1], 1)
        self.assertEqual(encode(quiet_fields())[-1], 0)

    def test_write_num_items_as_the_il_states(self):
        for count, head in ((127, bytes([127])), (128, bytes([0x80, 0x80])), (300, bytes([0x81, 0x2C]))):
            with self.subTest(count=count):
                record = encode(quiet_fields(custom_data={f"{i:03}": "" for i in range(count)}))
                self.assertEqual(record[8:8 + len(head)], head)


class CodecAgreementTests(unittest.TestCase):
    def test_the_codec_writes_every_fixture_item_as_the_table_does(self):
        for data in (realistic_v33_player_data(), realistic_v34_player_data()):
            for item in data["inventory"]:
                with self.subTest(prefab=item["prefab"]):
                    out = BinaryWriter()
                    write_item(out, item, 110)
                    self.assertEqual(out.get_bytes(), encode(fields_of(item)))

    def test_a_table_record_reads_back_as_its_fields(self):
        record = encode(quiet_fields(**TRIGGERS, crafter_name="Hodr", prefab_hash=12345))
        item = read_item(BinaryReader(record), 110)
        self.assertEqual((item["quality"], item["stack"], item["variant"], item["crafter_name"]), (3, 7, 2, "Hodr"))
        self.assertEqual(item["_wire"]["prefab_hash"], 12345)


if __name__ == "__main__":
    unittest.main()
