"""Intel HEX handler run by unblob (FSD §11)."""

from pathlib import Path

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
