"""WiX/Burn pure core (FSD §9): the container walk over a .wixburn header."""

import importlib
import struct
from pathlib import Path
from types import ModuleType

import pytest
from unblob.file_utils import File, InvalidInputFormat
from unblob.report import CalculateChunkExceptionReport

from tests.conftest import FIXTURES, chunks, run_unblob
from unblob_installers._pe import find_section


def wix_burn() -> ModuleType:
    # Imported per test, so the file is collected before the module exists.
    return importlib.import_module("unblob_installers.wix_burn")


def header(stub: int, sig: tuple[int, int], sizes: list[int]) -> bytes:
    return struct.pack(
        f"<II16s6I{len(sizes)}I",
        0x00F14300,
        2,
        bytes(16),
        stub,
        0,
        *sig,
        1,
        len(sizes),
        *sizes,
    )


def test_tc_burn_07_container_walk_three_attached():
    walk = wix_burn().containers
    assert walk(header(0x1000, (0, 0), [100, 10, 20, 30])) == [
        ("u0.cab", 0x1000, 100),
        ("a0.cab", 0x1064, 10),
        ("a1.cab", 0x106E, 20),
        ("a2.cab", 0x1082, 30),
    ]
    # Signed: attached containers start after the original signature.
    assert walk(header(0x1000, (0x1068, 0x40), [100, 10, 20, 30]))[1:] == [
        ("a0.cab", 0x10A8, 10),
        ("a1.cab", 0x10B2, 20),
        ("a2.cab", 0x10C6, 30),
    ]


FIXTURE = FIXTURES / "burn" / "standard.exe"
COUNT_FIELD = 4 + 4 + 16 + 4 * 5  # magic, version, GUID, stub … format
SIZES = COUNT_FIELD + 4  # UX container size, then the attached ones


def patched(tmp_path: Path, offset: int, value: int) -> Path:
    """Write the Burn fixture with one u32 of its .wixburn header replaced."""
    data = bytearray(FIXTURE.read_bytes())
    with File.from_bytes(bytes(data)) as file:
        section = find_section(file, 0, b".wixburn")
    assert section is not None
    struct.pack_into("<I", data, section[0] + offset, value)
    path = tmp_path / "patched.exe"
    path.write_bytes(bytes(data))
    return path


def burn_outcome(path: Path, tmp_path: Path) -> tuple[list[str], list[str], list[str]]:
    """wix_burn chunks, exception reports, and the container files written."""
    result = run_unblob(path, tmp_path / "x", max_depth=1)
    reports = [r for t in result.results for r in t.reports]
    return (
        [c.handler_name for c in chunks(result) if c.handler_name == "wix_burn"],
        [
            type(r).__name__
            for r in reports
            if isinstance(r, CalculateChunkExceptionReport)
        ],
        [p.name for p in (tmp_path / "x").rglob("a*.cab")],
    )


def test_tc_burn_02_container_beyond_the_file_is_not_claimed(tmp_path: Path):
    assert burn_outcome(FIXTURE, tmp_path / "control")[0] == ["wix_burn"]

    oversized = patched(tmp_path, SIZES + 4, FIXTURE.stat().st_size)  # attached a0
    assert burn_outcome(oversized, tmp_path / "size") == ([], [], [])
    # unblob also drops a chunk past the end of the file; the handler rejects first.
    with File.from_path(oversized) as file, pytest.raises(InvalidInputFormat):
        wix_burn().WixBurnHandler().calculate_chunk(file, 0)

    with File.from_bytes(FIXTURE.read_bytes()) as file:
        section = find_section(file, 0, b".wixburn")
    assert section is not None
    too_many = patched(
        tmp_path, COUNT_FIELD, section[1] // 4
    )  # table beyond the section
    assert burn_outcome(too_many, tmp_path / "count") == ([], [], [])
