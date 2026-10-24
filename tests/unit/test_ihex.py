"""Intel HEX pure core (FSD §11): record validation and region naming."""

import importlib
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


@pytest.mark.xfail(reason="FR-HEX-02: ihex handler absent", strict=True)
def test_tc_hex_02_valid_fixture_parses_to_its_eof():
    assert ihex().chunk_end(FIXTURE, 0) == len(FIXTURE)


@pytest.mark.xfail(reason="FR-HEX-02: ihex handler absent", strict=True)
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


@pytest.mark.xfail(reason="FR-HEX-06: ihex handler absent", strict=True)
def test_tc_hex_06_region_file_name():
    assert str(ihex().region_name(0x08000000)) == "0x08000000.bin"
    assert str(ihex().region_name(0x00007E00)) == "0x00007e00.bin"
