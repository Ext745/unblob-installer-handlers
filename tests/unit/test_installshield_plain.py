"""InstallShield plain-layout handler (FSD §13a), unit tier, Wave 3."""

import struct
import tracemalloc
from pathlib import Path

import pytest
from unblob.file_utils import InvalidInputFormat
from unblob.models import File
from unblob.report import ExtractionProblem

from tests.installshield_plain_image import (
    IMAGE_END,
    ansi,
    minimal_pe,
    pe_with_sections,
    setup_exe,
    utf16,
)
from unblob_installers.installshield_plain import (
    InstallShieldPlainExtractor,
    InstallShieldPlainHandler,
)

MIB = 1024 * 1024


def test_tc_sec_06_plain_section_count_bounded():
    pe = pe_with_sections(65535)
    assert 2_600_000 < len(pe) < 2_700_000  # the "2.6 MB PE" of the contract
    tracemalloc.start()
    try:
        with File.from_bytes(pe) as file:
            try:
                chunk = InstallShieldPlainHandler().calculate_chunk(file, 0)
            except InvalidInputFormat:
                chunk = None  # FR-COM-01: raising or returning no chunk declines
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert chunk is None
    assert peak < 16 * MIB, f"{peak} bytes allocated"


# --- Wave 3: malformed overlays and names outside the extraction directory ---


def ansi_record(source: str, destination: str, version: str, length: str, data: bytes):
    fields = (source, destination, version, length)
    return b"".join(f.encode("latin-1") + b"\0" for f in fields) + data


THREE = [
    (
        f"f{n}.bin",
        f"Disk1\\f{n}.bin",
        "1.0.0.0",  # scrub:allow version number
        bytes([n]) * 100,
    )
    for n in range(3)
]


def ansi_three(third_length: str | None = None) -> bytes:
    records = [ansi_record(s, d, v, str(len(x)), x) for s, d, v, x in THREE]
    if third_length is not None:
        s, d, v, x = THREE[2]
        records[2] = ansi_record(s, d, v, third_length, x)
    return setup_exe(b"".join(records))


def utf16_count_4_with_3() -> bytes:
    package = bytearray(utf16(THREE))
    struct.pack_into("<I", package, 0, 4)
    return setup_exe(bytes(package))


def last_record_one_byte_long() -> bytes:
    s, d, v, x = THREE[2]
    head = b"".join(ansi_record(*r[:3], str(len(r[3])), r[3]) for r in THREE[:2])
    return setup_exe(head + ansi_record(s, d, v, str(len(x) + 1), x))


DECLINED = {
    "no overlay": lambda: bytes(minimal_pe()),
    "UTF-16 count 4 with 3 records": utf16_count_4_with_3,
    "ANSI first length 12a": lambda: setup_exe(
        ansi_record(
            "a.bin",
            "Disk1\\a.bin",
            "1.0.0.0",  # scrub:allow version number
            "12a",
            b"x" * 12,
        )
    ),
    "last record 1 byte past": last_record_one_byte_long,
}


@pytest.mark.parametrize("case", DECLINED)
def test_tc_isw_08_malformed_overlays_declined(case: str):
    # A plain File, not the ReadRecorder: this handler reads the PE through
    # struct.unpack_from, which needs the buffer protocol (Python 3.12+ for a
    # Python class). Its reads past the end are ruled out by _pe._unpack's
    # bounds check; one that slipped through would raise struct.error, which
    # the strict InvalidInputFormat expectation below fails on.
    data = DECLINED[case]()
    with File.from_bytes(data) as file:
        try:
            chunk = InstallShieldPlainHandler().calculate_chunk(file, 0)
        except InvalidInputFormat:
            chunk = None  # FR-COM-01: raising or returning no chunk declines
    assert chunk is None

    # An ANSI third record whose length field is 12a ends the package after
    # record 2 (FR-ISW-09); the intact package is claimed whole.
    whole = ansi_three()
    cut = ansi_three(third_length="12a")
    for data, end in (
        (whole, len(whole)),
        (
            cut,
            IMAGE_END
            + sum(len(ansi_record(*r[:3], str(len(r[3])), r[3])) for r in THREE[:2]),
        ),
    ):
        with File.from_bytes(data) as file:
            chunk = InstallShieldPlainHandler().calculate_chunk(file, 0)
        assert chunk is not None
        assert (chunk.start_offset, chunk.end_offset) == (0, end)


BAD_NAMES = ["..\\..\\evil.txt", "C:\\evil.txt", "\\\\server\\x"]


@pytest.mark.parametrize("layout", ["ansi", "utf16"])
def test_tc_sec_08_plain_names_outside_rejected(layout: str, tmp_path: Path):
    build = ansi if layout == "ansi" else utf16
    good = [
        (
            "in.bin",
            "Disk1\\inside.txt",
            "1.0.0.0",  # scrub:allow version number
            b"inside",
        ),
        ("last.bin", "last.txt", "1.0.0.0", b"last"),  # scrub:allow version number
    ]
    bad = [
        (f"e{n}.bin", name, "1.0.0.0", b"evil")  # scrub:allow version number
        for n, name in enumerate(BAD_NAMES)
    ]
    base = tmp_path / "x"
    base.mkdir()
    source = base / "in.exe"
    source.write_bytes(setup_exe(build([good[0], *bad, good[1]])))
    out = base / "out"
    out.mkdir()
    result = InstallShieldPlainExtractor().extract(source, out)
    problems = [
        r.problem
        for r in (result.reports if result else [])
        if isinstance(r, ExtractionProblem)
    ]
    assert len(problems) == len(BAD_NAMES)
    for name, problem in zip(BAD_NAMES, problems, strict=True):
        assert repr(name) in problem
    # Nothing beside or above the extraction directory; the others extracted.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["x"]
    assert sorted(p.name for p in base.iterdir()) == ["in.exe", "out"]
    written = {
        p.relative_to(out).as_posix(): p.read_bytes()
        for p in out.rglob("*")
        if p.is_file()
    }
    assert written == {"Disk1/inside.txt": b"inside", "last.txt": b"last"}
