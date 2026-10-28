"""MCUboot handler run by unblob (FSD §13)."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import INPUTS, chunks, run_unblob

FIXTURE = INPUTS["mcuboot"] / "standard.bin"
OFFSET = 0x10000


def flash_dump(tmp_path: Path) -> Path:
    image = FIXTURE.read_bytes()
    dump = tmp_path / "flash.bin"
    dump.write_bytes(b"\xff" * OFFSET + image + b"\xff" * 0x10000)
    return dump


def mcuboot_chunks(result):
    return [c for c in chunks(result) if c.handler_name == "mcuboot"]


def test_tc_mcb_01_found_at_its_offset_in_a_flash_dump(tmp_path: Path):
    found = mcuboot_chunks(run_unblob(flash_dump(tmp_path), tmp_path / "x"))
    assert [c.start_offset for c in found] == [OFFSET]


def test_tc_mcb_02_chunk_ends_after_the_tlv_area(tmp_path: Path):
    found = mcuboot_chunks(run_unblob(flash_dump(tmp_path), tmp_path / "x"))
    assert [c.end_offset for c in found] == [OFFSET + FIXTURE.stat().st_size]


def test_tc_mcb_04_split_into_header_image_tlv(tmp_path: Path, payload: bytes):
    run_unblob(FIXTURE, tmp_path)
    out = next(tmp_path.rglob("image.bin")).parent
    header, image, tlv = (
        (out / n).read_bytes() for n in ("header.bin", "image.bin", "tlv.bin")
    )
    assert len(header) == 0x20
    assert image == payload
    assert header + image + tlv == FIXTURE.read_bytes()


def test_tc_mcb_05_report_version_load_address_flags(tmp_path: Path):
    (chunk,) = mcuboot_chunks(run_unblob(FIXTURE, tmp_path))
    (report,) = [
        r.model_dump()
        for r in chunk.extraction_reports
        if r.__typename__ == "MCUbootImageReport"
    ]
    assert (report["version"], report["load_address"], report["flags"]) == (
        "1.2.3+4",
        0,
        0,
    )


def test_tc_mcb_08_encrypted_image_written_as_ciphertext(
    tmp_path: Path, payload: bytes
):
    imgtool = shutil.which("imgtool")
    if imgtool is None:
        pytest.skip("precondition unmet: imgtool (oracles) not installed")
    encrypted = INPUTS["mcuboot"] / "encrypted.bin"
    info = subprocess.run(
        [imgtool, "dumpinfo", str(encrypted)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert re.search(r"^flags:\s+ENCRYPTED_AES128", info, re.M)
    header_size, image_size = (
        int(m[1], 16)
        for m in (
            re.search(rf"^{f}:\s+(0x[0-9a-f]+)", info, re.M)
            for f in ("hdr_size", "img_size")
        )
        if m
    )

    run_unblob(encrypted, tmp_path)
    image = next(tmp_path.rglob("image.bin")).read_bytes()

    data = encrypted.read_bytes()
    assert image == data[header_size : header_size + image_size]
    assert image != payload
