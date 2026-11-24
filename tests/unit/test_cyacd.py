"""Cypress .cyacd and Infineon .cyacd2 chunk recognition (FSD §13e), unit tier."""

from pathlib import Path

import pytest
from unblob.file_utils import InvalidInputFormat
from unblob.models import ExtractError, File
from unblob.report import ErrorReport

from tests.conftest import INPUTS
from tests.cyacd_image import SILICON_ID, SILICON_REV, data_line, row_line
from tests.read_recorder import ReadRecorder
from unblob_installers.cyacd import (
    Cyacd2Extractor,
    Cyacd2Handler,
    CyacdExtractor,
    CyacdHandler,
)

KIB = 1024

PREAMBLE = b"unrelated line one\nsecond line\nthird line\n"


def fixture(handler: str, name: str) -> bytes:
    return (INPUTS[handler] / name).read_bytes()


def test_tc_cya_01_unit_cyacd_header_line():
    cyacd = fixture("cyacd", "standard.cyacd")
    chunk = CyacdHandler().calculate_chunk(
        File.from_bytes(PREAMBLE + cyacd), len(PREAMBLE)
    )
    assert chunk is not None
    assert (chunk.start_offset, chunk.end_offset) == (
        len(PREAMBLE),
        len(PREAMBLE) + len(cyacd),
    )


@pytest.mark.parametrize(
    "data,start",
    [
        (b"0123456789AB\n:this is not a row\n", 0),
        (b"FF0123456789AB\n:00000000800\n", 2),  # inside a longer hex run
    ],
)
def test_tc_cya_01_unit_not_a_cyacd(data: bytes, start: int):
    with pytest.raises(InvalidInputFormat):
        CyacdHandler().calculate_chunk(File.from_bytes(data), start)


def test_tc_cya_10_unit_cyacd2_header_line():
    cyacd2 = fixture("cyacd2", "standard.cyacd2")
    data = PREAMBLE + cyacd2
    chunk = Cyacd2Handler().calculate_chunk(File.from_bytes(data), len(PREAMBLE))
    assert chunk is not None
    assert (chunk.start_offset, chunk.end_offset) == (len(PREAMBLE), len(data))


@pytest.mark.parametrize("variant", ["version 02", "cyacd file"])
def test_tc_cya_10_unit_not_a_cyacd2(variant: str):
    if variant == "version 02":
        data = b"02" + fixture("cyacd2", "standard.cyacd2")[2:]
    else:
        data = fixture("cyacd", "standard.cyacd")
    with pytest.raises(InvalidInputFormat):
        Cyacd2Handler().calculate_chunk(File.from_bytes(data), 0)


# --- Wave 3: malformed rows and lines, overlaps, output and read bounds -----

ROW_DATA = [bytes([n]) * 128 for n in range(4)]
HEADER2 = fixture("cyacd2", "standard.cyacd2").split(b"\n", 2)[:2]  # header, @APPINFO


def cyacd_text(rows: list[bytes]) -> bytes:
    return (
        b"\r\n".join([f"{SILICON_ID:08X}{SILICON_REV:02X}00".encode(), *rows]) + b"\r\n"
    )


def cyacd2_text(lines: list[bytes]) -> bytes:
    return b"\n".join([*HEADER2, *lines]) + b"\n"


def end_after(text: bytes, line: bytes) -> int:
    """Offset just past the terminator of the line holding `line`."""
    return text.index(b"\n", text.index(line) + len(line)) + 1


def bad_checksum(line: bytes) -> bytes:
    return line[:-2] + f"{(int(line[-2:], 16) + 1) & 0xFF:02X}".encode()


def bad_length(line: bytes) -> bytes:
    # data length field (raw bytes 3-4, hex digits 7-10) one larger, checksum fixed
    raw = bytearray.fromhex(line[1:].decode())
    raw[3:5] = (int.from_bytes(raw[3:5], "big") + 1).to_bytes(2, "big")
    raw[-1] = -sum(raw[:-1]) & 0xFF
    return b":" + raw.hex().upper().encode()


@pytest.mark.parametrize(
    "damage", [bad_checksum, bad_length], ids=["checksum", "length"]
)
def test_tc_cya_02_bad_row_ends_the_chunk(damage):
    rows = [row_line(0, n, data) for n, data in enumerate(ROW_DATA)]
    text = cyacd_text([rows[0], rows[1], damage(rows[2]), rows[3]])
    chunk = CyacdHandler().calculate_chunk(File.from_bytes(text), 0)
    assert chunk is not None
    assert (chunk.start_offset, chunk.end_offset) == (0, end_after(text, rows[1]))
    # The same damage on the first row leaves no valid row: declined.
    first_bad = cyacd_text([damage(rows[0]), *rows[1:]])
    with pytest.raises(InvalidInputFormat):
        CyacdHandler().calculate_chunk(File.from_bytes(first_bad), 0)


@pytest.mark.parametrize(
    "bad",
    [
        data_line(0x10000200, b"\x33" * 16) + b"0",  # odd digit count
        b"@APPINFO:1234",  # an @ line of neither §13e.1 form
        b":" + b"0" * 9,  # 9 digits: shorter than address plus one byte
    ],
    ids=["odd", "appinfo-1234", "9-digit"],
)
def test_tc_cya_08_bad_line_ends_the_chunk(bad: bytes):
    lines = [data_line(0x10000000 + 0x10 * n, bytes([n]) * 16) for n in range(3)]
    text = cyacd2_text([lines[0], lines[1], bad, lines[2]])
    chunk = Cyacd2Handler().calculate_chunk(File.from_bytes(text), 0)
    assert chunk is not None
    assert (chunk.start_offset, chunk.end_offset) == (0, end_after(text, lines[1]))
    # The same line first: no valid data line, declined.
    with pytest.raises(InvalidInputFormat):
        Cyacd2Handler().calculate_chunk(File.from_bytes(cyacd2_text([bad, *lines])), 0)


def extract2(tmp_path: Path, text: bytes) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True)
    source = tmp_path / "in.cyacd2"
    source.write_bytes(text)
    out = tmp_path / "out"
    out.mkdir()
    return source, out


def test_tc_cya_09_overlapping_lines(tmp_path: Path):
    a = data_line(0x10000000, b"\x11" * 16)
    clash = data_line(0x10000008, b"\x22" * 4)  # rewrites bytes 8-11 of line 3
    source, out = extract2(tmp_path / "clash", cyacd2_text([a, clash]))
    with pytest.raises(ExtractError) as raised:
        Cyacd2Extractor().extract(source, out)
    errors = [r for r in raised.value.reports if isinstance(r, ErrorReport)]
    assert errors, raised.value.reports
    assert "lines 3 and 4" in str(errors[0])  # header 1, @APPINFO 2
    assert not any(out.iterdir())  # the last write did not win

    same = data_line(0x10000008, b"\x11" * 4)  # identical bytes: accepted
    source, out = extract2(tmp_path / "same", cyacd2_text([a, same]))
    Cyacd2Extractor().extract(source, out)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == {
        "0x10000000.bin": b"\x11" * 16
    }


@pytest.mark.parametrize("kind", ["cyacd2", "cyacd"])
def test_tc_sec_02_cyacd_output_never_exceeds_the_chunk(kind: str, tmp_path: Path):
    if kind == "cyacd2":
        text = cyacd2_text(
            [data_line(0x00000000, b"\x11" * 16), data_line(0xFFFFFF00, b"\x22" * 16)]
        )
        extractor = Cyacd2Extractor()
    else:
        text = cyacd_text(
            [row_line(0, 0, ROW_DATA[0]), row_line(0, 0xFFFF, ROW_DATA[1])]
        )
        extractor = CyacdExtractor()
    source = tmp_path / f"in.{kind}"
    source.write_bytes(text)
    out = tmp_path / "out"
    out.mkdir()
    extractor.extract(source, out)
    written = [p for p in out.rglob("*") if p.is_file()]
    assert len(written) == 2  # two regions, no fill between them
    assert sum(p.stat().st_size for p in written) <= len(text)


@pytest.mark.parametrize(
    "kind", ["cyacd data length FFFF", "cyacd2 without line breaks"]
)
def test_tc_sec_03_cyacd_declined_within_the_file(kind: str):
    if kind == "cyacd data length FFFF":
        raw = bytes([0, 0, 0, 0xFF, 0xFF]) + b"\x00" * 16
        row = b":" + (raw + bytes([-sum(raw) & 0xFF])).hex().upper().encode()
        data = cyacd_text([row]).ljust(KIB, b"0")
        handler = CyacdHandler()
    else:
        data = (HEADER2[0] + b"0" * KIB)[:KIB]  # 1 KiB of hex digits, no newline
        handler = Cyacd2Handler()
    assert len(data) == KIB
    with ReadRecorder(data) as file, pytest.raises(InvalidInputFormat):
        handler.calculate_chunk(file, 0)
    assert not file.read_past_end, f"asked for byte {file.highest} of {file.size()}"
