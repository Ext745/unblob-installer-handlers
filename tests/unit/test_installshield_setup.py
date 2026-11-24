"""InstallShield headered single-file packages (FSD §13a), unit tier, Wave 3."""

import hashlib
import os
import struct
import tracemalloc
import zlib
from collections.abc import Callable
from pathlib import Path

import pytest
from unblob.file_utils import InvalidInputFormat
from unblob.report import ExtractionProblem

from tests.installshield_setup_image import M1024, Member, classic, obfuscate, stream
from tests.read_recorder import ReadRecorder
from unblob_installers.installshield_setup import (
    InstallShieldSetupHandler,
    PftwExtractor,
)

HEADER = 46
CLASSIC_RECORD = 0x138
STREAM_RECORD = 0x18
ONE = [Member("one.txt", b"first member\r\n")]
TWO = [*ONE, Member("two.txt", b"second member\r\n")]


def chunk_of(data: bytes):
    with ReadRecorder(data) as file:
        chunk = InstallShieldSetupHandler().calculate_chunk(file.as_file(), 0)
    assert not file.read_past_end
    assert chunk is not None
    return chunk


def patched(data: bytes, offset: int, fmt: str, value: int) -> bytes:
    out = bytearray(data)
    struct.pack_into(fmt, out, offset, value)
    return bytes(out)


def stream_name_length(length: int) -> bytes:
    """Build a stream package whose first record declares the given name length."""
    return patched(stream(ONE), HEADER, "<I", length)


def unpaired_surrogate() -> bytes:
    data = bytearray(stream(ONE))
    name = HEADER + STREAM_RECORD  # "one.txt" in UTF-16LE
    data[name : name + 2] = b"\x00\xd8"  # a high surrogate followed by "n"
    return bytes(data)


MALFORMED = {
    "file count 0": lambda: patched(classic(TWO), 0x0E, "<H", 0),
    "layout type 5": lambda: patched(classic(TWO), 0x10, "<I", 5),
    # the last member's data length (classic record + 0x10C) 1 byte past the input
    "last member 1 byte past": lambda: patched(
        classic(TWO),
        len(classic(ONE)) + 0x10C,
        "<I",
        len(TWO[1].content) + 1,
    ),
    "classic record cut": lambda: classic(TWO)[: len(classic(ONE)) + 0x100],
    "stream name past the input": lambda: stream(ONE)[: HEADER + STREAM_RECORD + 6],
    "empty name": lambda: classic([Member("", b"nameless")]),
    "stream name length 0": lambda: stream_name_length(0),
    "stream name length 3": lambda: stream_name_length(3),
    "stream name length 520": lambda: stream_name_length(520),
    "unpaired surrogate": unpaired_surrogate,
}


@pytest.mark.parametrize("case", MALFORMED)
def test_tc_isw_03_malformed_packages_declined(case: str):
    # Controls: the unmodified packages are claimed whole.
    for good in (classic(TWO), stream(ONE)):
        chunk = chunk_of(good)
        assert (chunk.start_offset, chunk.end_offset) == (0, len(good))
    # Boundary control: a 518-byte (259-character) stream name is accepted.
    long_name = stream([Member("a" * 259, b"x")])
    assert chunk_of(long_name).end_offset == len(long_name)

    data = MALFORMED[case]()
    with ReadRecorder(data) as file, pytest.raises(InvalidInputFormat):
        InstallShieldSetupHandler().calculate_chunk(file.as_file(), 0)
    assert not file.read_past_end, f"asked for byte {file.highest} of {file.size()}"


def extract(tmp_path: Path, data: bytes) -> tuple[list[ExtractionProblem], Path]:
    tmp_path.mkdir(parents=True)
    source = tmp_path / "in.pftw"
    source.write_bytes(data)
    out = tmp_path / "out"
    out.mkdir()
    result = PftwExtractor().extract(source, out)
    problems = [
        r
        for r in (result.reports if result else [])
        if isinstance(r, ExtractionProblem)
    ]
    return problems, out


def files_under(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_tc_isw_05_cut_zlib_member_reported(tmp_path: Path):
    content = bytes(range(256)) * 64
    cut = zlib.compress(content)
    cut = cut[: len(cut) // 2]
    first = Member("first.bin", b"before the cut member")
    last = Member("last.bin", b"after the cut member")
    # The cut member: its stored bytes are the obfuscated half stream; the
    # deflated marker (record + 0x16) is set afterwards, so the generator does
    # not compress it again.
    data = bytearray(stream([first, Member("cut.bin", cut, M1024), last]))
    record = len(stream([first]))
    struct.pack_into("<H", data, record + 0x16, 1)
    assert obfuscate(cut, b"cut.bin", 1024) in data

    problems, out = extract(tmp_path / "x", bytes(data))
    assert [(p.problem, p.path) for p in problems] == [
        ("member failed to inflate", "cut.bin")
    ]
    assert files_under(out) == {
        "first.bin": first.content,
        "cut.bin": cut,  # de-obfuscated, not inflated, not the inflated prefix
        "last.bin": last.content,
    }


BAD_NAMES = ["..\\..\\evil.txt", "C:\\evil.txt", "\\\\server\\x"]


@pytest.mark.parametrize("layout", ["classic", "stream"])
def test_tc_sec_08_setup_names_outside_rejected(layout: str, tmp_path: Path):
    build = classic if layout == "classic" else stream
    good = [Member("ok\\inside.txt", b"inside"), Member("last.txt", b"last")]
    members = [good[0]] + [Member(n, b"evil") for n in BAD_NAMES] + [good[1]]
    problems, out = extract(tmp_path / "x", build(members))
    names = [p.problem for p in problems]
    assert len(names) == len(BAD_NAMES)
    for bad, problem in zip(BAD_NAMES, names, strict=True):
        assert repr(bad if layout == "stream" else bad.encode()) in problem
    # Nothing beside or above the extraction directory; the others extracted.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["x"]
    assert sorted(p.name for p in (tmp_path / "x").iterdir()) == ["in.pftw", "out"]
    assert files_under(out) == {"ok/inside.txt": b"inside", "last.txt": b"last"}


MIB = 1 << 20


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(MIB):
            digest.update(block)
    return digest.hexdigest()


@pytest.mark.parametrize(
    "name,content,flags",
    [
        # Unobfuscated: inflate is fed the reader's full-size slices, the
        # case that held 32 MiB per slice before NFR-SEC-11.
        ("zeros.bin", lambda: bytes(64 * MIB), 0),
        ("random.bin", lambda: os.urandom(8 * MIB), M1024),
    ],
)
def test_tc_sec_11_member_inflate_bounded(
    name: str, content: Callable[[], bytes], flags: int, tmp_path: Path
):
    data = content()
    expected = hashlib.sha256(data).hexdigest()
    package = stream([Member(name, data, flags, deflated=True)])
    del data
    tracemalloc.start()
    try:
        problems, out = extract(tmp_path / "x", package)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert problems == []
    assert sha256_of(out / name) == expected
    assert peak <= MIB, f"{peak} bytes held"
