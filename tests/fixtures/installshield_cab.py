"""Write a self-contained InstallShield cabinet of the version 5 layout.

Usage: python3 installshield_cab.py <payload file> <output .cab>

The layout is as unshield 1.6.2 reads it (lib/cabfile.h, lib/libunshield.c,
lib/file.c, lib/file_group.c; MIT): a 20-byte common header, a 40-byte
volume header, the cabinet descriptor at 0x200 holding the file table, one
file group and the strings, then the file data. Two files in directory
"app" of file group "Firmware": firmware.bin compressed (64 KiB raw-deflate
chunks, each with a 2-byte length) and readme.txt stored. Version 5 keeps no
MD5, so none is written. Deterministic: same payload, same bytes.
"""

import struct
import sys
import zlib
from pathlib import Path

SIGNATURE = b"ISc("
VERSION = 0x01000004  # (version >> 12) & 0xF == 0: the version 5 layout
DESCRIPTOR_OFFSET = 0x200
FILE_TABLE_OFFSET = 0x280  # relative to the descriptor, after its 0x276 bytes
FILE_COMPRESSED = 0x4
CHUNK = 64 * 1024
README = b"Firmware image for the unblob-installer-handlers test suite.\n"


def compress(data: bytes) -> bytes:
    out = b""
    for at in range(0, len(data), CHUNK):
        z = zlib.compressobj(9, zlib.DEFLATED, -15)
        block = z.compress(data[at : at + CHUNK]) + z.flush()
        out += struct.pack("<H", len(block)) + block
    return out


def cabinet(payload: bytes) -> bytes:
    files = [  # (name, stored bytes, expanded size, flags)
        ("firmware.bin", compress(payload), len(payload), FILE_COMPRESSED),
        ("readme.txt", README, len(README), 0),
    ]

    # File table region, offsets relative to its start: one directory entry,
    # one entry per file, then the descriptors and the strings.
    count = 1 + len(files)
    descriptors_at = 4 * count
    strings_at = descriptors_at + 0x3A * len(files)
    strings = b"app\0"
    name_offsets = []
    for name, *_ in files:
        name_offsets.append(strings_at + len(strings))
        strings += name.encode() + b"\0"
    table_size = strings_at + len(strings)

    # File group, offsets relative to the descriptor: an offset-list entry,
    # the group descriptor (name, 0x48 bytes, first and last file), its name.
    group_list_at = FILE_TABLE_OFFSET + table_size
    group_at = group_list_at + 12
    group_name_at = group_at + 4 + 0x48 + 8
    group = (
        struct.pack("<III", group_name_at, group_at, 0)
        + struct.pack("<I", group_name_at)
        + bytes(0x48)
        + struct.pack("<II", 0, len(files) - 1)
        + b"Firmware\0"
    )
    descriptor_size = group_list_at + len(group)
    data_at = DESCRIPTOR_OFFSET + descriptor_size

    table = struct.pack("<I", strings_at)  # directory 0's name
    table += b"".join(
        struct.pack("<I", descriptors_at + 0x3A * i) for i in range(len(files))
    )
    offset = data_at
    for (_, stored, expanded, flags), name_at in zip(files, name_offsets, strict=True):
        table += (
            struct.pack("<IIHII", name_at, 0, flags, expanded, len(stored))
            + bytes(0x14)
            + struct.pack("<I", offset)
            + bytes(16)  # MD5, unused by version 5
        )
        offset += len(stored)
    table += strings

    fields = bytearray(FILE_TABLE_OFFSET)
    struct.pack_into("<I", fields, 0x0C, FILE_TABLE_OFFSET)
    struct.pack_into("<II", fields, 0x14, table_size, table_size)
    struct.pack_into("<I", fields, 0x1C, 1)  # directories
    struct.pack_into("<I", fields, 0x28, len(files))
    struct.pack_into("<I", fields, 0x3E, group_list_at)  # file_group_offsets[0]
    descriptor = bytes(fields) + table + group

    head = struct.pack(
        "<4sIIII", SIGNATURE, VERSION, 0, DESCRIPTOR_OFFSET, descriptor_size
    )
    volume = struct.pack("<10I", data_at, 0, 0, len(files) - 1, 0, 0, 0, 0, 0, 0)
    data = b"".join(stored for _, stored, _, _ in files)
    return (head + volume).ljust(DESCRIPTOR_OFFSET, b"\0") + descriptor + data


if __name__ == "__main__":
    Path(sys.argv[2]).write_bytes(cabinet(Path(sys.argv[1]).read_bytes()))
