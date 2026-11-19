"""InstallShield cabinet layout checks (FSD §6) on hand-built headers."""

import struct

import pytest
from unblob.file_utils import File, InvalidInputFormat

from tests.conftest import INPUTS
from tests.samples import handler

V21 = 0x04000834  # InstallShield 2015+ (the Realtek set's version)


@pytest.mark.parametrize("descriptor_size", [0, 29456], ids=["data-cab", "hdr"])
def test_tc_isc_06_v6_cabinet_file_not_claimed(descriptor_size: int):
    header = struct.pack("<4sIIII", b"ISc(", V21, 0, 0x200, descriptor_size)
    data = header + bytes(0x200 + descriptor_size)
    with (
        File.from_bytes(data) as file,
        pytest.raises(InvalidInputFormat, match="version 5"),
    ):
        handler("installshield").calculate_chunk(file, 0)


# FR-ISC-07: malformed version 5 descriptors, built on the fixture cabinet.
FIXTURE = INPUTS["installshield"] / "standard.cab"
DESC_OFFSET, DESC_SIZE = 12, 16  # within the 20-byte common header
VOLUME = 20  # the 40-byte version 5 volume header follows the common header


def _patched(offset: int, value: int, data: bytes | None = None) -> bytes:
    out = bytearray(FIXTURE.read_bytes() if data is None else data)
    struct.pack_into("<I", out, offset, value)
    return bytes(out)


def _forged_101() -> bytes:
    # BookCatKid/unblob#1: descriptor offset 0x14, size 1, and a volume header
    # saying the last file's data ends at byte 101.
    blob = bytearray(101)
    struct.pack_into("<4sIIII", blob, 0, b"ISc(", 0x01000004, 0, 0x14, 1)
    struct.pack_into("<I", blob, VOLUME + 7 * 4, 100)
    struct.pack_into("<I", blob, VOLUME + 9 * 4, 1)
    return bytes(blob)


def _descriptor_past_input() -> bytes:
    data = FIXTURE.read_bytes()
    (offset,) = struct.unpack_from("<I", data, DESC_OFFSET)
    return _patched(DESC_SIZE, len(data) - offset + 1)


def _descriptor_moved_to_0x3c() -> bytes:
    # The same descriptor copied to 0x3C: the file table is relative to the
    # descriptor and the file data offsets to the cabinet, so it stays valid.
    data = bytearray(FIXTURE.read_bytes())
    offset, size = struct.unpack_from("<II", data, DESC_OFFSET)
    data[0x3C : 0x3C + size] = data[offset : offset + size]
    struct.pack_into("<I", data, DESC_OFFSET, 0x3C)
    return bytes(data)


CASES = [  # (build, claimed): malformed inputs, then the boundary controls
    pytest.param(_forged_101, False, id="forged-101-bytes"),
    pytest.param(
        lambda: _patched(DESC_OFFSET, 0x14),
        False,
        id="descriptor-at-0x14",
    ),
    pytest.param(
        lambda: _patched(DESC_OFFSET, 0x3B),
        False,
        id="descriptor-at-0x3b",
    ),
    pytest.param(
        lambda: _patched(DESC_SIZE, 0x275),
        False,
        id="descriptor-size-0x275",
    ),
    pytest.param(_descriptor_past_input, False, id="descriptor-past-input"),
    pytest.param(_descriptor_moved_to_0x3c, True, id="control-descriptor-at-0x3c"),
    pytest.param(lambda: _patched(DESC_SIZE, 0x276), True, id="control-size-0x276"),
]


@pytest.mark.parametrize("build, claimed", CASES)
def test_tc_isc_10_malformed_v5_descriptor_not_claimed(build, claimed: bool):
    data = build()
    with File.from_bytes(data) as file:
        if not claimed:
            with pytest.raises(InvalidInputFormat):
                handler("installshield").calculate_chunk(file, 0)
            return
        chunk = handler("installshield").calculate_chunk(file, 0)
    assert chunk is not None
    assert (chunk.start_offset, chunk.end_offset) == (0, len(data))
