"""Inno Setup handler (FSD §7), unit tier: the offset-table search window."""

import struct
import zlib

import pytest
from unblob.file_utils import InvalidInputFormat
from unblob.models import File

from tests.installshield_plain_image import minimal_pe
from unblob_installers.inno import SEARCH_LIMIT, InnoSetupHandler

TABLE_ID = b"nS5W7dT\x83\xaa\x1b\x0fj"  # Inno 5.1.5 and later


def installer(table_at: int) -> bytes:
    """Build a minimal PE, zeros, then a valid revision-1 offset table at table_at.

    TotalSize, the table's first field, is the input's length, so a claimed
    chunk runs to the end of the input.
    """
    tail = 12 + 4 + 24 + 4  # ID, revision, six u32 fields, CRC
    size = table_at + tail
    body = TABLE_ID + struct.pack("<I", 1) + struct.pack("<6I", size, 0, 0, 0, 0, 0)
    table = body + struct.pack("<I", zlib.crc32(body))
    pe = bytes(minimal_pe())
    data = pe + bytes(table_at - len(pe)) + table
    assert len(data) == size
    return data


def test_tc_inno_05_table_id_inside_the_window_is_claimed():
    assert SEARCH_LIMIT == 16 * 1024 * 1024
    data = installer(SEARCH_LIMIT - 12)  # the ID's last byte is the window's last
    with File.from_bytes(data) as file:
        chunk = InnoSetupHandler().calculate_chunk(file, 0)
    assert chunk is not None
    assert (chunk.start_offset, chunk.end_offset) == (0, len(data))


def test_tc_inno_05_table_id_past_the_window_is_declined():
    data = installer(SEARCH_LIMIT - 11)  # the ID's last byte is 1 past the window
    with File.from_bytes(data) as file, pytest.raises(InvalidInputFormat):
        InnoSetupHandler().calculate_chunk(file, 0)
