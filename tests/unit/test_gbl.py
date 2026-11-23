"""Silicon Labs GBL v3 chunk calculation (FSD §13d)."""

import struct

import pytest
from unblob.models import File

from tests.conftest import INPUTS
from tests.gbl_image import END_TAG, METADATA, recrc, tags_of
from unblob_installers.gbl import GblHandler


def short_stream() -> bytes:
    """standard.gbl's tags plus a METADATA tag, ending 2 bytes before a 4-byte multiple."""
    gbl = (INPUTS["gbl"] / "standard.gbl").read_bytes()
    tag_id, offset, length = tags_of(gbl)[-1]
    assert tag_id == END_TAG
    tags = gbl[: offset + length - 12]
    n = 4 + (2 - len(tags) - 8 - 12) % 4
    stream = recrc(tags + struct.pack("<II", METADATA, n) + b"m" * n + bytes(12))
    assert len(stream) % 4 == 2
    return stream


@pytest.mark.parametrize(
    "after,taken",
    [
        (b"\xff\xff\xff\x00", 2),  # padding stops at the 4-byte multiple
        (b"\xff", 1),  # input ends: the 0xFF bytes that are there
        (b"\xff\x00", 1),
        (b"\xfe\xff", 0),
        (b"", 0),
    ],
)
def test_tc_gbl_03_unit_padding_bounds(after: bytes, taken: int):
    stream = short_stream()
    chunk = GblHandler().calculate_chunk(File.from_bytes(stream + after), 0)
    assert chunk is not None
    assert chunk.start_offset == 0
    assert chunk.end_offset == len(stream) + taken  # the end tag's CRC is inside


def test_tc_gbl_03_unit_padding_bounds_embedded():
    stream = short_stream()
    data = b"\x00" * 7 + stream + b"\xff\xff\xff"
    chunk = GblHandler().calculate_chunk(File.from_bytes(data), 7)
    assert chunk is not None
    # The padding counts from the GBL start, not the input start.
    assert (chunk.start_offset, chunk.end_offset) == (7, 7 + len(stream) + 2)
