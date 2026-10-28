"""UF2 pure core (FSD §10): block recognition and region naming."""

import importlib
import struct
from pathlib import Path
from types import ModuleType

import pytest
from unblob.file_utils import File
from unblob.models import ExtractError
from unblob.report import ErrorReport, Report

MAGIC_START0, MAGIC_START1, MAGIC_END = 0x0A324655, 0x9E5D5157, 0x0AB16F30
FLAG_FAMILY = 0x00002000
FLAG_NOT_MAIN = 0x00000001
RP2040 = 0xE48BFF56


def uf2() -> ModuleType:
    # Imported per test, so the file is collected before the module exists.
    return importlib.import_module("unblob_installers.uf2")


def block(
    addr: int,
    data: bytes,
    n: int = 0,
    total: int = 1,
    flags: int = FLAG_FAMILY,
    family: int = RP2040,
) -> bytes:
    head = struct.pack(
        "<8I",
        MAGIC_START0,
        MAGIC_START1,
        flags,
        addr,
        len(data),
        n,
        total,
        family if flags & FLAG_FAMILY else 0,
    )
    return head + data.ljust(476, b"\0") + struct.pack("<I", MAGIC_END)


def test_tc_uf2_01_block_recognised_by_three_magics():
    b = uf2().parse_block(block(0x10000000, b"\xaa" * 256))
    assert b is not None
    assert (b.target_addr, b.payload, b.family_id) == (
        0x10000000,
        b"\xaa" * 256,
        RP2040,
    )


def test_tc_uf2_05_region_file_name():
    assert str(uf2().region_path(RP2040, 0x10000000)) == "RP2040/0x10000000.bin"
    assert str(uf2().region_path(RP2040, 0x0000ABCD)) == "RP2040/0x0000abcd.bin"


def extract(tmp_path: Path, *blocks: bytes) -> dict[str, bytes]:
    """Run the UF2 extractor on the blocks; every output file and its bytes."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "in.uf2"
    source.write_bytes(b"".join(blocks))
    out = tmp_path / "out"
    out.mkdir()
    uf2().UF2Extractor().extract(source, out)
    return {
        str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()
    }


def test_tc_uf2_06_family_directory_for_missing_and_unknown_ids(tmp_path: Path):
    assert extract(tmp_path / "none", block(0x2000, b"\x11" * 256, flags=0)) == {
        "no_family/0x00002000.bin": b"\x11" * 256
    }
    unknown = block(0x2000, b"\x22" * 256, family=0x12345678)
    assert extract(tmp_path / "unknown", unknown) == {
        "0x12345678/0x00002000.bin": b"\x22" * 256
    }


def test_tc_uf2_07_not_main_flash_block_contributes_nothing(tmp_path: Path):
    files = extract(
        tmp_path,
        block(0x1000, b"\xaa" * 256, 0, 3),
        block(0x1100, b"\xbb" * 256, 1, 3, flags=FLAG_FAMILY | FLAG_NOT_MAIN),
        block(0x1200, b"\xcc" * 256, 2, 3),
    )
    assert b"\xbb" not in b"".join(files.values())
    assert files == {
        "RP2040/0x00001000.bin": b"\xaa" * 256,
        "RP2040/0x00001200.bin": b"\xcc" * 256,
    }


def test_tc_uf2_03_oversized_payload_ends_the_chunk_before_its_block():
    good = [block(0x1000 + 256 * n, bytes([n]) * 256, n, 5) for n in range(5)]
    # Block 3 declares 477 payload bytes, one more than its 476-byte data field.
    bad = bytearray(good[3])
    struct.pack_into("<I", bad, 16, 477)
    data = b"".join([*good[:3], bytes(bad), good[4]])
    with File.from_bytes(data) as file:
        chunk = uf2().UF2Handler().calculate_chunk(file, 0)
    assert chunk is not None
    assert (chunk.start_offset, chunk.end_offset) == (0, 3 * 512)


def extract_raising(
    tmp_path: Path, *blocks: bytes
) -> tuple[tuple[Report, ...], list[Path]]:
    """Run the extractor expecting ExtractError; its reports and the files written."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "in.uf2"
    source.write_bytes(b"".join(blocks))
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ExtractError) as raised:
        uf2().UF2Extractor().extract(source, out)
    return raised.value.reports, [p for p in out.rglob("*") if p.is_file()]


def test_tc_uf2_08_conflicting_duplicate_fails_naming_both_blocks(tmp_path: Path):
    reports, written = extract_raising(
        tmp_path,
        block(0x1000, b"\xaa" * 256, 0, 4),
        block(0x1100, b"\xbb" * 256, 1, 4),
        block(0x1200, b"\xcc" * 256, 2, 4),
        block(0x1100, b"\xdd" * 256, 3, 4),  # rewrites block 1's bytes
    )
    errors = [r for r in reports if isinstance(r, ErrorReport)]
    assert errors, reports
    assert "blocks 1 and 3" in str(errors[0])
    assert written == []  # the last write did not win, nothing was written


def test_tc_uf2_11_identical_duplicates_extract_once(tmp_path: Path):
    files = extract(
        tmp_path,
        block(0x1000, b"\xaa" * 256, 0, 4),
        block(0x1100, b"\xbb" * 256, 1, 4),
        block(0x1000, b"\xaa" * 256, 2, 4),  # same address, same bytes
        block(0x1180, b"\xbb" * 64, 3, 4),  # inside block 1, same bytes
    )
    assert files == {"RP2040/0x00001000.bin": b"\xaa" * 256 + b"\xbb" * 256}


@pytest.mark.parametrize("field", [0, 4, 508], ids=["start0", "start1", "end"])
def test_tc_uf2_12_block_with_one_bad_magic_not_accepted(field: int):
    good = block(0x10000000, b"\xaa" * 256)
    assert uf2().parse_block(good) is not None
    bad = bytearray(good)
    bad[field] ^= 0xFF
    assert uf2().parse_block(bytes(bad)) is None
    # In a run, the chunk ends before the block with the bad magic.
    run = b"".join(block(0x1000 + 256 * n, bytes([n]) * 256, n, 3) for n in range(2))
    with File.from_bytes(run + bytes(bad)) as file:
        chunk = uf2().UF2Handler().calculate_chunk(file, 0)
    assert chunk is not None
    assert (chunk.start_offset, chunk.end_offset) == (0, 2 * 512)


ESP32S3 = 0xC47E5767


def test_tc_uf2_13_families_never_share_a_file(tmp_path: Path):
    # Two families writing different bytes at the same addresses: each keeps
    # its own region file, and neither is a conflict.
    files = extract(
        tmp_path,
        block(0x1000, b"\xaa" * 256, 0, 4),
        block(0x1000, b"\x55" * 256, 1, 4, family=ESP32S3),
        block(0x1100, b"\xbb" * 256, 2, 4),
        block(0x1100, b"\x66" * 256, 3, 4, family=ESP32S3),
    )
    assert files == {
        "RP2040/0x00001000.bin": b"\xaa" * 256 + b"\xbb" * 256,
        "ESP32S3/0x00001000.bin": b"\x55" * 256 + b"\x66" * 256,
    }
