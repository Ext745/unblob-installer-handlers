"""NSIS handler (FSD §13b), unit tier, Wave 3: CRC check and header bounds."""

import struct
import tracemalloc
from pathlib import Path

from unblob.file_utils import InvalidInputFormat
from unblob.models import File
from unblob.report import ExtractionProblem

from tests.conftest import INPUTS
from tests.installshield_plain_image import pe_with_sections
from unblob_installers._nsis import NSIS_FLAG_NO_CRC, NSISExtractor
from unblob_installers.nsis import NSISHandler

FIXTURE = (INPUTS["nsis"] / "standard.exe").read_bytes()
FIRSTHEADER = FIXTURE.index(b"\xef\xbe\xad\xdeNullsoftInst") - 4  # flags first
MIB = 1024 * 1024


def nsis_end(data: bytes) -> int:
    """End of the NSIS data: firstheader offset + its length of following data."""
    return FIRSTHEADER + struct.unpack_from("<I", data, FIRSTHEADER + 24)[0]


def extract(tmp_path: Path, data: bytes) -> tuple[list[str], dict[str, bytes]]:
    tmp_path.mkdir(parents=True)
    source = tmp_path / "in.exe"
    source.write_bytes(data)
    out = tmp_path / "out"
    out.mkdir()
    result = NSISExtractor().extract(source, out)
    problems = [
        r.problem
        for r in (result.reports if result else [])
        if isinstance(r, ExtractionProblem)
    ]
    files = {
        str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()
    }
    return problems, files


def test_tc_nsis_05_crc_mismatch_reported(tmp_path: Path):
    assert struct.unpack_from("<I", FIXTURE, FIRSTHEADER)[0] & NSIS_FLAG_NO_CRC == 0
    end = nsis_end(FIXTURE)
    assert end == len(FIXTURE)  # unsigned: the stored CRC is the last 4 bytes
    stored = struct.unpack_from("<I", FIXTURE, end - 4)[0]

    # The unmodified fixture: no CRC problem (the CRC is taken over the right range).
    problems, files = extract(tmp_path / "clean", FIXTURE)
    assert problems == []
    assert files

    # One byte of the stored CRC flipped: a problem naming both, files still extracted.
    flipped = bytearray(FIXTURE)
    flipped[end - 4] ^= 0xFF
    problems, damaged_files = extract(tmp_path / "flipped", bytes(flipped))
    bad = struct.unpack_from("<I", flipped, end - 4)[0]
    assert problems == [
        f"NSIS installer CRC mismatch: stored {bad:#010x}, computed {stored:#010x}"
    ]
    assert damaged_files == files

    # The same with flag 4 (no CRC) set: no CRC problem.
    struct.pack_into(
        "<I",
        flipped,
        FIRSTHEADER,
        struct.unpack_from("<I", flipped, FIRSTHEADER)[0] | NSIS_FLAG_NO_CRC,
    )
    problems, unchecked_files = extract(tmp_path / "no-crc", bytes(flipped))
    assert problems == []
    assert unchecked_files == files


def test_tc_sec_06_nsis_section_count_bounded():
    pe = pe_with_sections(65535)
    assert 2_600_000 < len(pe) < 2_700_000  # the "2.6 MB PE" of the contract
    tracemalloc.start()
    try:
        with File.from_bytes(pe) as file:
            try:
                chunk = NSISHandler().calculate_chunk(file, 0)
            except InvalidInputFormat:
                chunk = None  # FR-COM-01: raising or returning no chunk declines
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert chunk is None
    assert peak < 16 * MIB, f"{peak} bytes allocated"
