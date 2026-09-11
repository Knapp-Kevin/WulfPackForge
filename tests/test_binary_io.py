import unittest

from subscripts.binaryIO import BinaryReader, BinaryWriter
from subscripts.saveErrors import SaveFormatError


class BytePrimitiveTests(unittest.TestCase):
    def test_byte_and_ushort_round_trip_at_their_bounds(self):
        writer = BinaryWriter()
        for value in (0, 255):
            writer.write_byte(value)
        for value in (0, 65535):
            writer.write_ushort(value)
        reader = BinaryReader(writer.get_bytes())
        self.assertEqual([reader.read_byte(), reader.read_byte()], [0, 255])
        self.assertEqual([reader.read_ushort(), reader.read_ushort()], [0, 65535])
        reader.require_exhausted("primitives")

    def test_out_of_range_byte_and_ushort_are_refused_by_name(self):
        writer = BinaryWriter()
        with self.assertRaises(SaveFormatError) as byte_error:
            writer.write_byte(256)
        with self.assertRaises(SaveFormatError) as ushort_error:
            writer.write_ushort(65536)
        with self.assertRaises(SaveFormatError):
            writer.write_byte(-1)
        self.assertIn("byte", str(byte_error.exception))
        self.assertIn("255", str(byte_error.exception))
        self.assertIn("65535", str(ushort_error.exception))
        self.assertEqual(writer.get_bytes(), b"", "a refused value must not be partially written")


if __name__ == "__main__":
    unittest.main()
