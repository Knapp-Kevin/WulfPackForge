"""Little-endian binary reader and writer matching Valheim's ZPackage layout."""
import io
import struct

from subscripts.saveErrors import SaveFormatError

STRING_ERRORS = "surrogateescape"


class BinaryReader:
    def __init__(self, data: bytes):
        self.stream = io.BytesIO(data)
        self._length = len(data)

    def read_bytes(self, n: int) -> bytes:
        if n < 0:
            raise SaveFormatError(f"Negative length {n} in save data.")
        data = self.stream.read(n)
        if len(data) != n:
            raise SaveFormatError(f"Unexpected end of save data: wanted {n} bytes, got {len(data)}.")
        return data

    def read_int32(self) -> int:
        return struct.unpack("<i", self.read_bytes(4))[0]

    def read_float(self) -> float:
        return struct.unpack("<f", self.read_bytes(4))[0]

    def read_bool(self) -> bool:
        return self.read_bytes(1)[0] != 0

    def read_long(self) -> int:
        return struct.unpack("<q", self.read_bytes(8))[0]

    def read_vector3(self) -> list:
        return list(struct.unpack("<fff", self.read_bytes(12)))

    def read_7bit_encoded_int(self) -> int:
        value = 0
        for shift in range(0, 35, 7):
            byte = self.read_bytes(1)[0]
            value |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                return value
        raise SaveFormatError("Malformed 7-bit encoded integer in save data.")

    def read_string(self) -> str:
        length = self.read_7bit_encoded_int()
        return self.read_bytes(length).decode("utf-8", errors=STRING_ERRORS)

    def read_byte_array(self) -> bytes:
        return self.read_bytes(self.read_int32())

    def read_float_dict(self) -> dict:
        return {self.read_string(): self.read_float() for _ in range(self.read_int32())}

    def require_exhausted(self, context: str) -> None:
        remaining = self._length - self.stream.tell()
        if remaining:
            raise SaveFormatError(f"{remaining} unconsumed bytes after the {context}.")


class BinaryWriter:
    def __init__(self):
        self.stream = io.BytesIO()

    def get_bytes(self) -> bytes:
        return self.stream.getvalue()

    def write_bytes(self, data: bytes):
        self.stream.write(data)

    def write_int32(self, val: int):
        self.stream.write(struct.pack("<i", val))

    def write_float(self, val: float):
        self.stream.write(struct.pack("<f", val))

    def write_bool(self, val: bool):
        self.stream.write(b"\x01" if val else b"\x00")

    def write_long(self, val: int):
        self.stream.write(struct.pack("<q", val))

    def write_vector3(self, val: list):
        self.stream.write(struct.pack("<fff", *val))

    def write_7bit_encoded_int(self, value: int):
        while value >= 0x80:
            self.stream.write(bytes([(value & 0x7F) | 0x80]))
            value >>= 7
        self.stream.write(bytes([value]))

    def write_string(self, val: str):
        encoded = val.encode("utf-8", errors=STRING_ERRORS)
        self.write_7bit_encoded_int(len(encoded))
        self.stream.write(encoded)

    def write_byte_array(self, data: bytes):
        self.write_int32(len(data))
        self.stream.write(data)

    def write_float_dict(self, values: dict):
        self.write_int32(len(values))
        for key, value in values.items():
            self.write_string(key)
            self.write_float(value)
