"""Zigbee OTA upgrade file handler run by unblob (FSD §13c), Wave 1."""

import random
from pathlib import Path

import pytest
from unblob.report import UnknownChunkReport

from tests.conftest import chunks, run_unblob
from tests.zigbee_ota_image import (
    FILE_VERSION,
    HEADER_STRING,
    IMAGE_TYPE,
    MANUFACTURER,
    STACK_VERSION,
    build,
    standard,
)


def ota_chunks(result):
    return [c for c in chunks(result) if c.handler_name == "zigbee_ota"]


@pytest.mark.parametrize("field_control", [0, 1, 2, 4, 7])
def test_tc_zota_01_found_at_its_identifier(
    field_control: int, payload: bytes, tmp_path: Path
):
    ota = build([(0x0000, payload)], field_control=field_control)
    rng = random.Random(1301)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "embedded.bin"
    sample.write_bytes(rng.randbytes(0x1000) + ota + rng.randbytes(0x100))
    found = ota_chunks(run_unblob(sample, tmp_path / "x"))
    assert [(c.start_offset, c.end_offset) for c in found] == [
        (0x1000, 0x1000 + len(ota))
    ]


def test_tc_zota_02_chunk_ends_at_total_image_size(payload: bytes, tmp_path: Path):
    ota = standard(payload)
    rng = random.Random(1302)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "trailing.bin"
    sample.write_bytes(ota + rng.randbytes(4096))
    result = run_unblob(sample, tmp_path / "x")
    assert [(c.start_offset, c.end_offset) for c in ota_chunks(result)] == [
        (0, len(ota))
    ]
    unknown = [
        (r.start_offset, r.end_offset)
        for t in result.results
        if t.task.path == sample
        for r in t.reports
        if isinstance(r, UnknownChunkReport)
    ]
    assert unknown == [(len(ota), len(ota) + 4096)]


def test_tc_zota_04_one_file_per_sub_element(tmp_path: Path):
    subs = [
        (0x0000, b"first upgrade image"),
        (0x0001, b"signature-bytes" * 4),
        (0xF000, b"manufacturer"),
        (0x0000, b"second upgrade image"),
    ]
    sample = tmp_path / "tags.ota"
    sample.write_bytes(build(subs))
    run_unblob(sample, tmp_path / "x")
    out = next((tmp_path / "x").rglob("tag_0x0000_0.bin")).parent
    assert sorted(p.name for p in out.iterdir()) == [
        "tag_0x0000_0.bin",
        "tag_0x0000_3.bin",
        "tag_0x0001_1.bin",
        "tag_0xf000_2.bin",
    ]
    for index, (tag, data) in enumerate(subs):
        assert (out / f"tag_0x{tag:04x}_{index}.bin").read_bytes() == data


def test_tc_zota_05_report_carries_header_fields(payload: bytes, tmp_path: Path):
    sample = tmp_path / "standard.ota"
    sample.write_bytes(standard(payload))
    (chunk,) = ota_chunks(run_unblob(sample, tmp_path / "x"))
    (report,) = [
        r.model_dump()
        for r in chunk.extraction_reports
        if r.__typename__ == "ZigbeeOtaReport"
    ]
    assert report == {
        **report,
        "manufacturer_code": MANUFACTURER,
        "image_type": IMAGE_TYPE,
        "file_version": FILE_VERSION,
        "stack_version": STACK_VERSION,
        "header_string": HEADER_STRING.decode(),
    }
