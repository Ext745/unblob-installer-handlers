"""Intel HEX pure core (FSD §11): record validation and region naming."""

import importlib
from pathlib import Path
from types import ModuleType

import pytest

from tests.conftest import FIXTURES

FIXTURE = (FIXTURES / "ihex" / "standard.hex").read_bytes()


def ihex() -> ModuleType:
    # Imported per test, so the file is collected before the module exists.
    return importlib.import_module("unblob_installers.ihex")


def mutate(line_no: int, column: int, new: bytes) -> bytes:
    """Replace one character (column within the record line) of the fixture."""
    lines = FIXTURE.split(b"\n")
    line = bytearray(lines[line_no])
    line[column : column + 1] = new
    lines[line_no] = bytes(line)
    return b"\n".join(lines)


def test_tc_hex_02_valid_fixture_parses_to_its_eof():
    assert ihex().chunk_end(FIXTURE, 0) == len(FIXTURE)


@pytest.mark.parametrize(
    "line_no, column, new, what",
    [
        (5, 42, b"0", "checksum nibble"),
        (5, 2, b"F", "byte count nibble"),
        (5, 8, b"6", "record type 06"),
        (0, 14, b"0", "checksum of the type-04 record"),
    ],
)
def test_tc_hex_02_corrupted_record_is_not_claimed(line_no, column, new, what):
    data = mutate(line_no, column, new)
    assert data != FIXTURE, what
    # Not claimed at all: no shorter chunk that stops before the bad record.
    assert ihex().chunk_end(data, 0) is None


def test_tc_hex_06_region_file_name():
    assert str(ihex().region_name(0x08000000)) == "0x08000000.bin"
    assert str(ihex().region_name(0x00007E00)) == "0x00007e00.bin"


def record(rtype: int, address: int, data: bytes) -> bytes:
    body = bytes([len(data), address >> 8, address & 0xFF, rtype]) + data
    return b":" + (body + bytes([-sum(body) & 0xFF])).hex().upper().encode()


def extract(tmp_path: Path, text: bytes) -> dict[str, bytes]:
    """Run the Intel HEX extractor on text; every output file and its bytes."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "in.hex"
    source.write_bytes(text)
    out = tmp_path / "out"
    out.mkdir()
    ihex().IntelHexExtractor().extract(source, out)
    return {
        str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()
    }


def test_tc_hex_04_lf_crlf_and_mixed_give_identical_regions(tmp_path: Path):
    lines = FIXTURE.rstrip(b"\n").split(b"\n")
    lf = b"\n".join(lines) + b"\n"
    crlf = b"\r\n".join(lines) + b"\r\n"
    mixed = b"".join(
        line + (b"\r\n" if i % 2 else b"\n") for i, line in enumerate(lines)
    )
    results = [
        extract(tmp_path / name, text)
        for name, text in [("lf", lf), ("crlf", crlf), ("mixed", mixed)]
    ]
    assert results[0]
    assert results[0] == results[1] == results[2]
    for text in (crlf, mixed):
        assert ihex().chunk_end(text, 0) == len(text)


def test_tc_hex_09_gap_between_base_addresses_gives_two_regions(tmp_path: Path):
    text = (
        b"\n".join(
            [
                record(0x04, 0, b"\x08\x00"),
                record(0x00, 0x0000, b"\x11" * 16),
                record(0x04, 0, b"\x08\x01"),
                record(0x00, 0x0000, b"\x22" * 16),
                record(0x01, 0, b""),
            ]
        )
        + b"\n"
    )
    assert extract(tmp_path, text) == {
        "0x08000000.bin": b"\x11" * 16,
        "0x08010000.bin": b"\x22" * 16,
    }
