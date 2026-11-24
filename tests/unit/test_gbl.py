"""Silicon Labs GBL v3 chunk calculation (FSD §13d)."""

import json
import lzma
import struct
import subprocess
import sys
import tracemalloc
from pathlib import Path

import lz4.block
import pytest
from unblob.file_utils import InvalidInputFormat
from unblob.models import ExtractError, File
from unblob.report import ErrorReport, ExtractionProblem

from tests.conftest import INPUTS
from tests.gbl_image import END_TAG, METADATA, recrc, tag, tags_of, with_end_tag
from tests.read_recorder import ReadRecorder
from unblob_installers.gbl import (
    DECOMPRESSED_CAP,
    HEADER_TAG,
    PROG,
    PROG_LZ4,
    PROG_LZMA,
    GblExtractor,
    GblHandler,
)

MIB = 1024 * 1024


def short_stream() -> bytes:
    """standard.gbl's tags plus a METADATA tag, ending 2 bytes before a 4-byte multiple."""
    gbl = (INPUTS["gbl"] / "standard.gbl").read_bytes()
    tag_id, offset, length = tags_of(gbl)[-1]
    assert tag_id == END_TAG
    tags = gbl[: offset + length - 12]
    n = 4 + (2 - len(tags) - 8 - 12) % 4
    stream = recrc(tags + struct.pack("<II", METADATA, n) + b"m" * n + bytes(12))
    assert len(stream) % 4 == 2
    return stream


@pytest.mark.parametrize(
    "after,taken",
    [
        (b"\xff\xff\xff\x00", 2),  # padding stops at the 4-byte multiple
        (b"\xff", 1),  # input ends: the 0xFF bytes that are there
        (b"\xff\x00", 1),
        (b"\xfe\xff", 0),
        (b"", 0),
    ],
)
def test_tc_gbl_03_unit_padding_bounds(after: bytes, taken: int):
    stream = short_stream()
    chunk = GblHandler().calculate_chunk(File.from_bytes(stream + after), 0)
    assert chunk is not None
    assert chunk.start_offset == 0
    assert chunk.end_offset == len(stream) + taken  # the end tag's CRC is inside


def test_tc_gbl_03_unit_padding_bounds_embedded():
    stream = short_stream()
    data = b"\x00" * 7 + stream + b"\xff\xff\xff"
    chunk = GblHandler().calculate_chunk(File.from_bytes(data), 7)
    assert chunk is not None
    # The padding counts from the GBL start, not the input start.
    assert (chunk.start_offset, chunk.end_offset) == (7, 7 + len(stream) + 2)


# --- Wave 3: malformed streams, overlaps, decompression and decoder bounds ---


def gbl(*tags: bytes) -> bytes:
    """Build a GBL v3 stream: header tag (version 3, type 0), the tags, end tag."""
    return with_end_tag(
        tag(HEADER_TAG, b"\x00\x00\x00\x03" + bytes(4)) + b"".join(tags)
    )


def prog(tag_id: int, address: int, data: bytes) -> bytes:
    return tag(tag_id, struct.pack("<I", address) + data)


def lzma_alone(data: bytes, dict_size: int | None = None) -> bytes:
    """Pack data in the .lzma alone form; dict_size rewrites the declared dictionary."""
    packed = bytearray(lzma.compress(data, format=lzma.FORMAT_ALONE, preset=0))
    if dict_size is not None:
        struct.pack_into("<I", packed, 1, dict_size)
    return bytes(packed)


def extract(tmp_path: Path, data: bytes):
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "in.gbl"
    source.write_bytes(data)
    out = tmp_path / "out"
    out.mkdir()
    result = GblExtractor().extract(source, out)
    files = {p.name: p.read_bytes() for p in out.iterdir()}
    return (result.reports if result else []), files


STANDARD = (INPUTS["gbl"] / "standard.gbl").read_bytes()


def standard_tags() -> bytes:
    """standard.gbl through its end tag, without padding."""
    tag_id, offset, length = tags_of(STANDARD)[-1]
    assert tag_id == END_TAG
    return STANDARD[: offset + length]


def flip_data_byte(stream: bytes) -> bytes:
    _, offset, _ = tags_of(stream)[1]
    return (
        stream[: offset + 4] + bytes([stream[offset + 4] ^ 0x01]) + stream[offset + 5 :]
    )


def drop_end_tag(stream: bytes) -> bytes:
    return stream[:-12]


def length_past_input(stream: bytes) -> bytes:
    _, offset, _ = tags_of(stream)[1]
    return stream[: offset - 4] + struct.pack("<I", len(stream)) + stream[offset:]


def header_and_end_only(stream: bytes) -> bytes:
    return with_end_tag(stream[:16])


@pytest.mark.parametrize(
    "damage", [flip_data_byte, drop_end_tag, length_past_input, header_and_end_only]
)
def test_tc_gbl_02_malformed_declined(damage):
    stream = standard_tags()
    with ReadRecorder(stream) as file:  # control: the undamaged stream is claimed
        chunk = GblHandler().calculate_chunk(file, 0)
    assert chunk is not None
    assert chunk.end_offset == len(stream)
    with ReadRecorder(damage(stream)) as file, pytest.raises(InvalidInputFormat):
        GblHandler().calculate_chunk(file, 0)
    assert not file.read_past_end


def test_tc_gbl_08_overlapping_program_data(tmp_path: Path):
    first = prog(PROG, 0x1000, b"\x11" * 32)
    differ = prog(PROG, 0x1010, b"\x22" * 32)  # bytes 16-31 of tag 1 rewritten
    with pytest.raises(ExtractError) as raised:
        extract(tmp_path / "differ", gbl(first, differ))
    errors = [r for r in raised.value.reports if isinstance(r, ErrorReport)]
    assert errors, raised.value.reports
    assert "tags 1 and 2" in str(errors[0])
    assert not any((tmp_path / "differ" / "out").iterdir())  # last write did not win

    same = prog(PROG, 0x1010, b"\x11" * 16 + b"\x33" * 16)  # overlap identical
    reports, files = extract(tmp_path / "same", gbl(first, same))
    assert reports == []
    assert files == {"0x00001000.bin": b"\x11" * 32 + b"\x33" * 16}


def compressed(codec: str, size: int) -> bytes:
    zeros = bytes(size)
    if codec == "lz4":
        return lz4.block.compress(zeros, store_size=False)
    return lzma_alone(zeros)


@pytest.mark.parametrize("codec", ["lz4", "lzma"])
def test_tc_sec_07_decompression_capped_per_tag(codec: str, tmp_path: Path):
    tag_id = PROG_LZ4 if codec == "lz4" else PROG_LZMA
    other = prog(PROG, 0x0, b"\x5a" * 64)
    # 16 MiB exactly: written whole.
    reports, files = extract(
        tmp_path / "cap",
        gbl(other, prog(tag_id, 0x1000_0000, compressed(codec, DECOMPRESSED_CAP))),
    )
    assert reports == []
    assert files == {
        "0x00000000.bin": b"\x5a" * 64,
        "0x10000000.bin": bytes(DECOMPRESSED_CAP),
    }
    # 16 MiB + 1: an extraction problem naming tag 2, nothing of it written,
    # the other tag's region written as if it were absent; at most 33 MiB held
    # (the decoders build the capped output, then copy it: 2 x cap + 1 MiB).
    over = gbl(
        other, prog(tag_id, 0x1000_0000, compressed(codec, DECOMPRESSED_CAP + 1))
    )
    tracemalloc.start()
    try:
        reports, files = extract(tmp_path / "over", over)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak <= 2 * DECOMPRESSED_CAP + MIB, f"{peak} bytes held"
    problems = [r for r in reports if isinstance(r, ExtractionProblem)]
    assert [p.problem.split(":")[0] for p in problems] == [
        f"GBL tag 2 (0x{tag_id:08x})"
    ]
    assert files == {"0x00000000.bin": b"\x5a" * 64}


# NFR-SEC-09 runs the extractor in a child process whose address space is
# limited to 1 GiB, so a decoder allocating a declared 4 GiB dictionary fails
# there (MemoryError) instead of being absorbed by overcommit.
_CHILD = """
import json, resource, sys, tracemalloc
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))
from unblob_installers.gbl import GblExtractor
source, out = Path(sys.argv[1]), Path(sys.argv[2])
tracemalloc.start()
try:
    result = GblExtractor().extract(source, out)
    error = None
except BaseException as exc:
    result, error = None, f"{type(exc).__name__}: {exc}"
peak = tracemalloc.get_traced_memory()[1]
print(json.dumps({
    "error": error,
    "peak": peak,
    "problems": [r.problem for r in (result.reports if result else [])],
    "files": {p.name: p.stat().st_size for p in out.iterdir()},
}))
"""


def run_limited(tmp_path: Path, data: bytes) -> dict:
    tmp_path.mkdir(parents=True)
    source = tmp_path / "in.gbl"
    source.write_bytes(data)
    out = tmp_path / "out"
    out.mkdir()
    done = subprocess.run(
        [sys.executable, "-c", _CHILD, str(source), str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    report = json.loads(done.stdout)
    region = out / "0x00010000.bin"
    report["region"] = region.read_bytes() if region.exists() else None
    return report


ZEROS = bytes(4096)


@pytest.mark.parametrize("over", [24 * MIB, 0xFFFFFFFF], ids=["24MiB", "0xFFFFFFFF"])
def test_tc_sec_09_lzma_decoder_memory_capped(over: int, tmp_path: Path):
    ok = prog(PROG_LZMA, 0x0001_0000, lzma_alone(ZEROS, 16 * MIB))
    bad = prog(PROG_LZMA, 0x0002_0000, lzma_alone(ZEROS, over))
    # The fixture of the row: the 16 MiB tag (index 1) and the over-limit one (2).
    run = run_limited(tmp_path / "both", gbl(ok, bad))
    assert run["error"] is None, run["error"]
    assert run["files"] == {"0x00010000.bin": len(ZEROS)}  # not lengthened
    assert run["region"] == ZEROS
    assert [p.split(":")[0] for p in run["problems"]] == [
        f"GBL tag 2 (0x{PROG_LZMA:08x})"
    ]
    # The over-limit tag alone, so the allocation peak is its own.
    alone = run_limited(tmp_path / "alone", gbl(prog(PROG, 0x0, b"\x5a"), bad))
    assert alone["error"] is None, alone["error"]
    assert alone["files"] == {"0x00000000.bin": 1}
    assert alone["peak"] < MIB, f"{alone['peak']} bytes allocated for the tag"


@pytest.mark.parametrize(
    "case", ["tag length 0xFFFFFFFF", "header tag cut", "tag cut by the input end"]
)
def test_tc_sec_03b_gbl_declined_within_the_file(case: str):
    stream = standard_tags()
    _, offset, _ = tags_of(stream)[1]
    data = {
        "tag length 0xFFFFFFFF": stream[: offset - 4] + b"\xff" * 4 + stream[offset:],
        "header tag cut": stream[:12],
        "tag cut by the input end": stream[: offset + 8],
    }[case]
    with ReadRecorder(data) as file, pytest.raises(InvalidInputFormat):
        GblHandler().calculate_chunk(file, 0)
    assert not file.read_past_end, f"asked for byte {file.highest} of {file.size()}"
