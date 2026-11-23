"""Cypress .cyacd and Infineon .cyacd2 handlers run by unblob (FSD §13e), Wave 1.

Fixtures: tests/integration/archive/cyacd{,2}/__input__, written by
tests/cyacd_image.py from the FSD.
"""

import random
from pathlib import Path

import pytest

from tests.conftest import INPUTS, chunks, run_unblob
from tests.cyacd_image import (
    APP_ID,
    APPINFO,
    CYACD2_FILES,
    CYACD_FILES,
    PRODUCT_ID,
    SILICON_ID,
    SILICON_REV,
)

PREAMBLE = b"unrelated line one\nsecond line: 12 words\n0123456789AB is not alone\n"


def fixture(handler: str, name: str) -> bytes:
    return (INPUTS[handler] / name).read_bytes()


def spans(result, name: str) -> list[tuple[int, int]]:
    return [
        (c.start_offset, c.end_offset) for c in chunks(result) if c.handler_name == name
    ]


def extracted(root: Path, suffix: str) -> Path:
    return next(p for p in root.rglob(f"*{suffix}_extract") if p.is_dir())


def test_tc_cya_01_cyacd_found_at_its_header_line(tmp_path: Path):
    cyacd = fixture("cyacd", "standard.cyacd")
    sample = tmp_path / "embedded.txt"
    sample.write_bytes(PREAMBLE + cyacd)
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    assert spans(result, "cyacd") == [(len(PREAMBLE), len(PREAMBLE) + len(cyacd))]
    assert spans(result, "ihex") == []
    assert spans(result, "cyacd2") == []


def test_tc_cya_01_intel_hex_stays_ihex(tmp_path: Path):
    hexfile = fixture("ihex", "standard.hex")
    sample = tmp_path / "standard.hex"
    sample.write_bytes(hexfile)
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    assert spans(result, "ihex") == [(0, len(hexfile))]
    assert spans(result, "cyacd") == []


def test_tc_cya_01_header_then_non_hex_row_not_claimed(tmp_path: Path):
    sample = tmp_path / "notes.txt"
    sample.write_bytes(b"0123456789AB\n:this is not a row\n")
    assert spans(run_unblob(sample, tmp_path / "x", max_depth=1), "cyacd") == []


def test_tc_cya_10_cyacd2_found_at_its_header_line(tmp_path: Path):
    cyacd2 = fixture("cyacd2", "standard.cyacd2")
    sample = tmp_path / "embedded.txt"
    sample.write_bytes(PREAMBLE + cyacd2)
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    assert spans(result, "cyacd2") == [(len(PREAMBLE), len(PREAMBLE) + len(cyacd2))]
    assert spans(result, "cyacd") == []


def test_tc_cya_10_file_version_02_not_claimed(tmp_path: Path):
    cyacd2 = fixture("cyacd2", "standard.cyacd2")
    assert cyacd2.startswith(b"01")
    sample = tmp_path / "v2.cyacd2"
    sample.write_bytes(b"02" + cyacd2[2:])
    assert spans(run_unblob(sample, tmp_path / "x", max_depth=1), "cyacd2") == []


def test_tc_cya_10_cyacd_not_claimed_by_cyacd2(tmp_path: Path):
    sample = tmp_path / "standard.cyacd"
    sample.write_bytes(fixture("cyacd", "standard.cyacd"))
    assert spans(run_unblob(sample, tmp_path / "x", max_depth=1), "cyacd2") == []


@pytest.mark.parametrize(
    "handler,name",
    [
        ("cyacd", "standard.cyacd"),
        ("cyacd2", "standard.cyacd2"),
        ("cyacd2", "encrypted.cyacd2"),
    ],
)
def test_tc_cya_03_chunk_ends_after_the_last_line(
    handler: str, name: str, tmp_path: Path
):
    data = fixture(handler, name)
    assert data.endswith(b"\n")
    rng = random.Random(1503)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "trailing.bin"
    sample.write_bytes(data + b"garbage\n" + rng.randbytes(4096))
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    assert spans(result, handler) == [(0, len(data))]
    unknown = [
        (r.start_offset, r.end_offset)
        for t in result.results
        if t.task.path == sample
        for r in t.reports
        if r.__class__.__name__ == "UnknownChunkReport"
    ]
    assert unknown == [(len(data), sample.stat().st_size)]


def test_tc_cya_04_rows_per_array_as_contiguous_files(payload: bytes, tmp_path: Path):
    sample = tmp_path / "standard.cyacd"
    sample.write_bytes(fixture("cyacd", "standard.cyacd"))
    run_unblob(sample, tmp_path / "x", max_depth=1)
    out = extracted(tmp_path / "x", ".cyacd")
    expected = {
        f"array_0x{a:02x}/0x{offset:08x}.bin": payload[part]
        for a, offset, part in CYACD_FILES
    }
    written = {
        str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()
    }
    assert written == expected
    assert len(expected["array_0x00/0x00000000.bin"]) == 512


def test_tc_cya_05_address_ranges_little_endian(payload: bytes, tmp_path: Path):
    sample = tmp_path / "standard.cyacd2"
    sample.write_bytes(fixture("cyacd2", "standard.cyacd2"))
    run_unblob(sample, tmp_path / "x", max_depth=1)
    out = extracted(tmp_path / "x", ".cyacd2")
    assert {p.name: p.read_bytes() for p in out.iterdir()} == {
        f"0x{address:08x}.bin": payload[part] for address, part in CYACD2_FILES
    }


def report_of(result, handler: str) -> dict:
    (chunk,) = [c for c in chunks(result) if c.handler_name == handler]
    (report,) = [
        r.model_dump()
        for r in chunk.extraction_reports
        if r.__typename__ == "CyacdReport"
    ]
    return report


def test_tc_cya_06_cyacd2_report_and_encrypted_data_as_stored(
    payload: bytes, tmp_path: Path
):
    sample = tmp_path / "encrypted.cyacd2"
    sample.write_bytes(fixture("cyacd2", "encrypted.cyacd2"))
    report = report_of(run_unblob(sample, tmp_path / "x", max_depth=1), "cyacd2")
    assert report == {
        **report,
        "silicon_id": SILICON_ID,
        "silicon_revision": SILICON_REV,
        "app_id": APP_ID,
        "product_id": PRODUCT_ID,
        "appinfo_address": APPINFO[0],
        "appinfo_length": APPINFO[1],
        "encrypted": True,
    }
    out = extracted(tmp_path / "x", ".cyacd2")
    for address, part in CYACD2_FILES:  # written as stored, not decrypted
        assert (out / f"0x{address:08x}.bin").read_bytes() == payload[part]


def test_tc_cya_06_cyacd_report_big_endian_silicon_id(tmp_path: Path):
    sample = tmp_path / "standard.cyacd"
    sample.write_bytes(fixture("cyacd", "standard.cyacd"))
    report = report_of(run_unblob(sample, tmp_path / "x", max_depth=1), "cyacd")
    assert (report["silicon_id"], report["silicon_revision"]) == (
        SILICON_ID,
        SILICON_REV,
    )


def test_tc_cya_06_unencrypted_cyacd2_not_reported_encrypted(tmp_path: Path):
    sample = tmp_path / "standard.cyacd2"
    sample.write_bytes(fixture("cyacd2", "standard.cyacd2"))
    report = report_of(run_unblob(sample, tmp_path / "x", max_depth=1), "cyacd2")
    assert report["encrypted"] is False
