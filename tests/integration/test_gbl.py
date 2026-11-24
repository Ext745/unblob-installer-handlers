"""Silicon Labs GBL v3 handler run by unblob (FSD §13d), Wave 1.

Fixtures: tests/integration/archive/gbl/__input__, built with pygbl by
tests/fixtures/build.sh (tests/gbl_image.py).
"""

import random
import struct
from pathlib import Path

import pytest

from tests.conftest import INPUTS, chunks, run_unblob
from tests.gbl_image import (
    APP_INFO,
    END_TAG,
    HEADER_TAG,
    METADATA,
    METADATA_BYTES,
    SIGNATURE,
    SIGNATURE_BYTES,
    STANDARD_REGIONS,
    recrc,
    tags_of,
)

FIXTURES = ["standard.gbl", "tags.gbl", "encrypted.gbl"]


def fixture(name: str) -> bytes:
    return (INPUTS["gbl"] / name).read_bytes()


def unpadded(gbl: bytes) -> bytes:
    """Return the tag stream through the end tag, without Commander's padding."""
    tag_id, offset, length = tags_of(gbl)[-1]
    assert tag_id == END_TAG
    return gbl[: offset + length]


def gbl_chunks(result):
    return [c for c in chunks(result) if c.handler_name == "gbl"]


def extracted(root: Path) -> Path:
    return next(p for p in root.rglob("*.gbl_extract") if p.is_dir())


@pytest.mark.parametrize("name", FIXTURES)
def test_tc_gbl_01_found_at_the_header_tag(name: str, tmp_path: Path):
    gbl = fixture(name)
    rng = random.Random(1401)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "embedded.bin"
    sample.write_bytes(rng.randbytes(0x1000) + gbl + rng.randbytes(0x100))
    found = gbl_chunks(run_unblob(sample, tmp_path / "x", max_depth=1))
    assert [(c.start_offset, c.end_offset) for c in found] == [
        (0x1000, 0x1000 + len(gbl))
    ]


def test_tc_gbl_01_version_4_declined(tmp_path: Path):
    gbl = bytearray(unpadded(fixture("standard.gbl")))
    assert struct.unpack_from("<II", gbl) == (HEADER_TAG, 8)
    assert gbl[8:12] == b"\x00\x00\x00\x03"
    gbl[8:12] = b"\x00\x00\x00\x04"
    sample = tmp_path / "v4.gbl"
    sample.write_bytes(recrc(bytes(gbl)))
    assert gbl_chunks(run_unblob(sample, tmp_path / "x", max_depth=1)) == []


@pytest.mark.parametrize(
    "padding,taken",
    [
        (b"\xff\xff", 2),  # exactly what the multiple of 4 needs
        (b"\xff", 1),  # fewer 0xFF bytes than needed: those that are there
        (b"\xfe\xff", 0),  # not 0xFF: no padding
        (b"", 0),
    ],
)
def test_tc_gbl_03_chunk_takes_the_padding_only(
    padding: bytes, taken: int, tmp_path: Path
):
    # standard.gbl's tags with a METADATA tag appended whose length makes the
    # stream end 2 bytes before a 4-byte multiple.
    tags = unpadded(fixture("standard.gbl"))[:-12]
    n = 4 + (2 - len(tags) - 8 - 12) % 4
    stream = recrc(tags + struct.pack("<II", METADATA, n) + b"m" * n + bytes(12))
    assert len(stream) % 4 == 2
    rng = random.Random(1403)  # noqa: S311 - fixed test data, not cryptography
    trailer = b"\x00" + rng.randbytes(4096)  # never 0xFF first
    sample = tmp_path / "padded.bin"
    sample.write_bytes(stream + padding + trailer)
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    end = len(stream) + taken
    assert [(c.start_offset, c.end_offset) for c in gbl_chunks(result)] == [(0, end)]
    unknown = [
        (r.start_offset, r.end_offset)
        for t in result.results
        if t.task.path == sample
        for r in t.reports
        if r.__class__.__name__ == "UnknownChunkReport"
    ]
    assert unknown == [(end, sample.stat().st_size)]


def test_tc_gbl_04_program_data_as_address_ranges(payload: bytes, tmp_path: Path):
    sample = tmp_path / "standard.gbl"
    sample.write_bytes(fixture("standard.gbl"))
    run_unblob(sample, tmp_path / "x", max_depth=1)
    out = extracted(tmp_path / "x")
    assert sorted(p.name for p in out.iterdir()) == [
        "0x00000000.bin",
        "0x00010000.bin",
    ]
    for address, part in STANDARD_REGIONS.items():
        assert (out / f"0x{address:08x}.bin").read_bytes() == payload[part]


def test_tc_gbl_05_other_tags_written_raw(tmp_path: Path):
    gbl = fixture("tags.gbl")
    sample = tmp_path / "tags.gbl"
    sample.write_bytes(gbl)
    run_unblob(sample, tmp_path / "x", max_depth=1)
    out = extracted(tmp_path / "x")
    stored = tags_of(gbl)
    assert [t[0] for t in stored] == [
        HEADER_TAG,
        APP_INFO,
        METADATA,
        SIGNATURE,
        END_TAG,
    ]
    expected = {
        f"tag_0x{tag_id:08x}_{index}.bin": gbl[offset : offset + length]
        for index, (tag_id, offset, length) in enumerate(stored)
        if index not in (0, len(stored) - 1)
    }
    assert {p.name: p.read_bytes() for p in out.iterdir()} == expected
    assert expected[f"tag_0x{METADATA:08x}_2.bin"] == METADATA_BYTES
    assert expected[f"tag_0x{SIGNATURE:08x}_3.bin"] == SIGNATURE_BYTES


ENCRYPTION_INIT = 0xFA0606FA
ENCRYPTED_PROG = 0xF90707F9


@pytest.mark.parametrize(
    "header_type,signed", [(0x1, False), (0x101, True)], ids=["unsigned", "signed"]
)
def test_tc_gbl_06_encrypted_written_raw_with_report(
    header_type: int, signed: bool, tmp_path: Path
):
    gbl = fixture("encrypted.gbl")
    tags = unpadded(gbl)
    assert struct.unpack_from("<II", tags, 8) == (0x03000000, 0x1)
    # Header bit 0: encrypted; bit 8: signed (FSD §13d).
    tags = recrc(tags[:12] + struct.pack("<I", header_type) + tags[16:])
    sample = tmp_path / "encrypted.gbl"
    sample.write_bytes(tags + gbl[len(tags) :])
    result = run_unblob(sample, tmp_path / "x", max_depth=1)

    (chunk,) = gbl_chunks(result)
    assert (chunk.start_offset, chunk.end_offset) == (0, len(gbl))  # FR-GBL-03
    # The GblReport alone: no error report beside it.
    assert [r.model_dump() for r in chunk.extraction_reports] == [
        {"__typename__": "GblReport", "encrypted": True, "signed": signed}
    ]

    stored = tags_of(tags)
    assert [t[0] for t in stored] == [
        HEADER_TAG,
        ENCRYPTION_INIT,
        *[ENCRYPTED_PROG] * 4,
        END_TAG,
    ]
    # Every tag but header and end written raw; no address-range file.
    expected = {
        f"tag_0x{tag_id:08x}_{index}.bin": tags[offset : offset + length]
        for index, (tag_id, offset, length) in enumerate(stored)
        if index not in (0, len(stored) - 1)
    }
    out = extracted(tmp_path / "x")
    assert {p.name: p.read_bytes() for p in out.iterdir()} == expected
