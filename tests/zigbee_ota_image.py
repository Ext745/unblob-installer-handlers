"""Build Zigbee OTA upgrade files for tests (FSD §13c), from the FSD alone.

Layout (FSD §13c.1, Zigbee Cluster Library OTA Upgrade cluster), all fields
little-endian: file identifier 0x0BEEF11E, header version 0x0100, header
length, field control, manufacturer code, image type, file version, Zigbee
stack version, 32-byte header string, total image size (56 bytes), then the
optional fields field control selects (bit 0: security credential version,
1 byte; bit 1: upgrade file destination, 8 bytes; bit 2: minimum and maximum
hardware version, 2 x u16), then the sub-elements: tag ID (u16), length
(u32), data.

Usage: python3 -m tests.zigbee_ota_image <out.ota>   (the committed fixture)
"""

import struct
import sys
from pathlib import Path

FILE_ID = 0x0BEEF11E
HEADER_VERSION = 0x0100
BASE_HEADER = struct.Struct("<IHHHHHIH32sI")  # 56 bytes
SUB_HEADER = struct.Struct("<HI")

MANUFACTURER = 0x1234
IMAGE_TYPE = 0x5678
FILE_VERSION = 0x01020304
STACK_VERSION = 0x0002
HEADER_STRING = b"uih zigbee ota fixture"


def optional_size(field_control: int) -> int:
    return (
        (1 if field_control & 1 else 0)
        + (8 if field_control & 2 else 0)
        + (4 if field_control & 4 else 0)
    )


def build(
    subelements: list[tuple[int, bytes]],
    *,
    field_control: int = 0,
    header_length: int | None = None,
    header_version: int = HEADER_VERSION,
    total_size: int | None = None,
    manufacturer: int = MANUFACTURER,
    image_type: int = IMAGE_TYPE,
    file_version: int = FILE_VERSION,
    stack_version: int = STACK_VERSION,
    header_string: bytes = HEADER_STRING,
) -> bytes:
    """Build an OTA file; header_length and total_size override the computed values."""
    optional = bytes(
        [0x02] * (1 if field_control & 1 else 0)
        + [0xAA] * (8 if field_control & 2 else 0)
        + [0x01, 0x00, 0x05, 0x00] * (1 if field_control & 4 else 0)
    )
    body = b"".join(SUB_HEADER.pack(tag, len(data)) + data for tag, data in subelements)
    hlen = BASE_HEADER.size + len(optional) if header_length is None else header_length
    total = hlen + len(body) if total_size is None else total_size
    header = BASE_HEADER.pack(
        FILE_ID,
        header_version,
        hlen,
        field_control,
        manufacturer,
        image_type,
        file_version,
        stack_version,
        header_string.ljust(32, b"\0"),
        total,
    )
    return header + optional + body


def standard(payload: bytes) -> bytes:
    """Build the committed fixture: upgrade image = payload, plus a manufacturer tag."""
    return build([(0x0000, payload), (0xF000, b"manufacturer-data")])


if __name__ == "__main__":
    here = Path(__file__).parent
    payload = (here / "fixtures" / "payload.bin").read_bytes()
    Path(sys.argv[1]).write_bytes(standard(payload))
