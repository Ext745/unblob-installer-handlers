"""Intel HEX handler run by unblob (FSD §11)."""

import random
from pathlib import Path

import pytest

from tests.conftest import FIXTURES, chunks, run_unblob

FIXTURE = FIXTURES / "ihex" / "standard.hex"


def test_tc_hex_01_chunk_from_first_colon_to_after_eof_line(tmp_path: Path):
    before = b"Release notes\n\nFirmware image follows: see below.\n"
    after = b"\nEnd of image. Checksums: see the header.\n"
    hexdata = FIXTURE.read_bytes()
    sample = tmp_path / "notes.txt"
    sample.write_bytes(before + hexdata + after)

    found = [
        c
        for c in chunks(run_unblob(sample, tmp_path / "x"))
        if c.handler_name == "ihex"
    ]

    assert [(c.start_offset, c.end_offset) for c in found] == [
        (len(before), len(before) + len(hexdata))
    ]


def test_tc_hex_05_one_region_at_the_type_04_base(tmp_path: Path, payload: bytes):
    run_unblob(FIXTURE, tmp_path)

    regions = sorted(tmp_path.rglob("0x*.bin"))
    assert [p.name for p in regions] == ["0x08000000.bin"]
    assert regions[0].read_bytes() == payload


@pytest.mark.xfail(
    strict=True,
    reason="the feature is not implemented: the pattern needs a line start, so a first record glued to binary is missed",
)
def test_tc_hex_10_first_record_after_binary_keeps_its_base(
    tmp_path: Path, payload: bytes
):
    # Firmware blobs carry HEX images without a line break before the first
    # record; that record is the type-04 base, so missing it moves the data.
    rng = random.Random(1010)  # noqa: S311 - fixed test data, not cryptography
    before = rng.randbytes(4096).replace(b"\n", b"\0")
    hexdata = FIXTURE.read_bytes()
    sample = tmp_path / "blob.bin"
    sample.write_bytes(before + hexdata)

    found = [
        c
        for c in chunks(run_unblob(sample, tmp_path / "x"))
        if c.handler_name == "ihex"
    ]

    assert [(c.start_offset, c.end_offset) for c in found] == [
        (len(before), len(before) + len(hexdata))
    ]
    regions = sorted((tmp_path / "x").rglob("0x*.bin"))
    assert [p.name for p in regions] == ["0x08000000.bin"]
    assert regions[0].read_bytes() == payload
