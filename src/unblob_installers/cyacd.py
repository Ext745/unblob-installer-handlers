"""Cypress/Infineon bootloader files, .cyacd and .cyacd2 (FSD §13e).

.cyacd (PSoC 3/4/5LP), big-endian: a header line of 12 hex digits (silicon
ID, silicon revision, checksum type), then one line per flash row: ':',
array ID, row number, data length, data, checksum. .cyacd2 (PSoC 6, PSoC 4,
DFU SDK), little-endian (Infineon DFU SDK guide, Appendix C): a header line
of 24 hex digits, optional @APPINFO and @EIV lines, then ':' address + data
lines. Lines end in LF or CR LF.
"""

import binascii
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from unblob.file_utils import InvalidInputFormat
from unblob.models import (
    ExtractError,
    Extractor,
    ExtractResult,
    File,
    Handler,
    HandlerDoc,
    HandlerType,
    Reference,
    Regex,
    ValidChunk,
)
from unblob.report import Report, UnknownError

from ._extract import require_whole_chunk
from ._regions import OverlapConflictError, assemble, region_name

# ':' + 2 hex digits per byte: array (1), row (2), length (2), data (<= 0xFFFF), checksum (1)
MAX_CYACD_LINE = 1 + 2 * (1 + 2 + 2 + 0xFFFF + 1)
# The longest .cyacd2 line read; real files carry rows of up to a few KiB.
MAX_CYACD2_LINE = MAX_CYACD_LINE
_HEX = re.compile(rb"[0-9A-Fa-f]*")
_APPINFO = re.compile(rb"@APPINFO:0x([0-9A-Fa-f]{1,8}),0x([0-9A-Fa-f]{1,8})")
_EIV = re.compile(rb"@EIV:((?:[0-9A-Fa-f]{2})*)")


class CyacdReport(Report):
    """Header values of a .cyacd or .cyacd2 file (FR-CYA-06)."""

    silicon_id: int
    silicon_revision: int
    app_id: int | None = None
    product_id: int | None = None
    appinfo_address: int | None = None
    appinfo_length: int | None = None
    encrypted: bool | None = None


class _Buffer(Protocol):
    def __len__(self) -> int: ...
    def __getitem__(self, key: slice, /) -> bytes: ...
    def find(self, sub: bytes, start: int, end: int, /) -> int: ...


def _lines(buf: _Buffer, pos: int, max_line: int):
    """Yield (line without terminator, offset after its terminator) from pos.

    Reads at most max_line bytes per line, so a huge input without newlines is
    never read whole (NFR-SEC-03). A line at the end of the input needs no
    terminator.
    """
    while pos < len(buf):
        newline = buf.find(b"\n", pos, pos + max_line + 2)
        if newline == -1:
            end = min(len(buf), pos + max_line + 2)
            if end < len(buf):
                return  # longer than any valid line
        else:
            end = newline + 1
        yield buf[pos:end].rstrip(b"\r\n"), end
        pos = end


def _is_hex(text: bytes) -> bool:
    return _HEX.fullmatch(text) is not None


def _at_line_start(buf: _Buffer, start: int) -> bool:
    return start == 0 or buf[start - 1 : start] == b"\n"


# --- .cyacd ----------------------------------------------------------------


@dataclass(frozen=True)
class Row:
    array_id: int
    row: int
    data: bytes
    line_no: int


def parse_row(line: bytes) -> tuple[int, int, bytes] | None:
    """(array ID, row number, data) of a valid .cyacd row line, or None (FR-CYA-02)."""
    if not line.startswith(b":") or len(line) % 2 != 1 or not _is_hex(line[1:]):
        return None
    raw = binascii.unhexlify(line[1:])
    if len(raw) < 6:
        return None
    length = int.from_bytes(raw[3:5], "big")
    if len(raw) != 5 + length + 1 or (-sum(raw[:-1]) & 0xFF) != raw[-1]:
        return None
    return raw[0], int.from_bytes(raw[1:3], "big"), raw[5:-1]


@dataclass
class CyacdFile:
    silicon_id: int
    silicon_revision: int
    end: int  # offset after the last valid row's terminator
    rows: list[Row] = field(default_factory=list)


def parse_cyacd(buf: _Buffer, start: int, *, keep_rows: bool) -> CyacdFile:
    """Parse the .cyacd file at start; InvalidInputFormat if not one."""
    if not _at_line_start(buf, start):
        raise InvalidInputFormat("header not at a line start")
    lines = _lines(buf, start, MAX_CYACD_LINE)
    header, _ = next(lines, (b"", 0))
    if len(header) != 12 or not _is_hex(header):
        raise InvalidInputFormat("not a .cyacd header line")
    result = CyacdFile(int(header[:8], 16), int(header[8:10], 16), end=start)
    for line_no, (line, end) in enumerate(lines, start=2):
        row = parse_row(line)
        if row is None:
            break
        result.end = end
        if keep_rows:
            result.rows.append(Row(*row, line_no))
    if result.end == start:
        raise InvalidInputFormat("no valid .cyacd row")
    return result


class CyacdExtractor(Extractor):
    def extract(self, inpath: Path, outdir: Path) -> ExtractResult | None:
        require_whole_chunk(CyacdHandler().calculate_chunk, inpath)
        info = parse_cyacd(inpath.read_bytes(), 0, keep_rows=True)
        by_array: dict[int, list[tuple[int, bytes, int]]] = {}
        for row in info.rows:
            by_array.setdefault(row.array_id, []).append(
                (row.row * len(row.data), row.data, row.line_no)
            )
        arrays = []
        for array_id, writes in sorted(by_array.items()):
            try:
                arrays.append((array_id, assemble(writes)))
            except OverlapConflictError as exc:
                problem = f".cyacd lines {exc.first} and {exc.second} write different bytes at array {array_id} offset 0x{exc.address:08x}"
                raise ExtractError(
                    UnknownError(exception=ValueError(problem))
                ) from None
        for array_id, regions in arrays:
            folder = outdir / f"array_0x{array_id:02x}"
            folder.mkdir(parents=True, exist_ok=True)
            for offset, data in regions:
                (folder / region_name(offset)).write_bytes(data)
        return ExtractResult(
            reports=[
                CyacdReport(
                    silicon_id=info.silicon_id, silicon_revision=info.silicon_revision
                )
            ]
        )


class CyacdHandler(Handler):
    NAME = "cyacd"
    # A 12-digit header line, then a row. Matches inside longer hex runs are
    # declined by calculate_chunk (header not at a line start).
    PATTERNS = [Regex(r"[0-9A-Fa-f]{12}\r?\n:")]
    EXTRACTOR = CyacdExtractor()
    DOC = HandlerDoc(
        name="Cypress .cyacd",
        description="Cypress bootloader file for PSoC 3/4/5LP: a header line and one checksummed text line per flash row; rows are written per flash array as files of contiguous rows.",
        handler_type=HandlerType.ARCHIVE,
        vendor="Cypress Semiconductor (Infineon)",
        references=[
            Reference(
                title="Infineon AN68272: PSoC 3, PSoC 4, and PSoC 5LP UART Bootloader (.cyacd format)",
                url="https://www.infineon.com/dgdl/Infineon-AN68272_PSoC_3_PSoC_4_PSoC_5LP_and_PSoC_Analog_Coprocessor_UART_Bootloader-ApplicationNotes-v12_00-EN.pdf",
            ),
            Reference(
                title="DefenseMouse/ohcya: .cyacd and .cyacd2 tools",
                url="https://github.com/DefenseMouse/ohcya",
            ),
        ],
        limitations=[
            "Rows are written at row number x row length per array, not at device addresses",
        ],
    )

    def calculate_chunk(self, file: File, start_offset: int) -> ValidChunk | None:
        info = parse_cyacd(file, start_offset, keep_rows=False)
        return ValidChunk(start_offset=start_offset, end_offset=info.end)


# --- .cyacd2 ---------------------------------------------------------------


@dataclass
class Cyacd2File:
    silicon_id: int
    silicon_revision: int
    app_id: int
    product_id: int
    end: int  # offset after the last valid data line's terminator
    appinfo: tuple[int, int] | None = None
    encrypted: bool = False
    writes: list[tuple[int, bytes, int]] = field(default_factory=list)


def parse_data_line(line: bytes) -> tuple[int, bytes] | None:
    """(address, data) of a valid .cyacd2 data line, or None (FR-CYA-08)."""
    if not line.startswith(b":") or len(line) < 11 or len(line) % 2 != 1:
        return None
    if not _is_hex(line[1:]):
        return None
    raw = binascii.unhexlify(line[1:])
    return int.from_bytes(raw[:4], "little"), raw[4:]


def _header2(line: bytes) -> Cyacd2File:
    if len(line) != 24 or not _is_hex(line) or line[:2] != b"01":
        raise InvalidInputFormat("not a .cyacd2 header line")
    raw = binascii.unhexlify(line)
    return Cyacd2File(
        silicon_id=int.from_bytes(raw[1:5], "little"),
        silicon_revision=raw[5],
        app_id=raw[7],
        product_id=int.from_bytes(raw[8:12], "little"),
        end=0,
    )


def _apply_at_line(info: Cyacd2File, line: bytes) -> bool:
    """Take an @APPINFO or @EIV line into info; False if it is neither."""
    if match := _APPINFO.fullmatch(line):
        info.appinfo = (int(match[1], 16), int(match[2], 16))
        return True
    if _EIV.fullmatch(line):
        info.encrypted = True
        return True
    return False


def parse_cyacd2(buf: _Buffer, start: int, *, keep_data: bool) -> Cyacd2File:
    """Parse the .cyacd2 file at start; InvalidInputFormat if not one."""
    if not _at_line_start(buf, start):
        raise InvalidInputFormat("header not at a line start")
    lines = _lines(buf, start, MAX_CYACD2_LINE)
    header, _ = next(lines, (b"", 0))
    info = _header2(header)
    info.end = start
    for line_no, (line, end) in enumerate(lines, start=2):
        if line.startswith(b"@"):
            if not _apply_at_line(info, line):
                break
            continue
        data = parse_data_line(line)
        if data is None:
            break
        info.end = end
        if keep_data:
            info.writes.append((*data, line_no))
    if info.end == start:
        raise InvalidInputFormat("no valid .cyacd2 data line")
    return info


class Cyacd2Extractor(Extractor):
    def extract(self, inpath: Path, outdir: Path) -> ExtractResult | None:
        require_whole_chunk(Cyacd2Handler().calculate_chunk, inpath)
        info = parse_cyacd2(inpath.read_bytes(), 0, keep_data=True)
        try:
            regions = assemble(info.writes)
        except OverlapConflictError as exc:  # FR-CYA-09
            problem = f".cyacd2 lines {exc.first} and {exc.second} write different bytes at 0x{exc.address:08x}"
            raise ExtractError(UnknownError(exception=ValueError(problem))) from None
        for address, data in regions:
            (outdir / region_name(address)).write_bytes(data)
        return ExtractResult(
            reports=[
                CyacdReport(
                    silicon_id=info.silicon_id,
                    silicon_revision=info.silicon_revision,
                    app_id=info.app_id,
                    product_id=info.product_id,
                    appinfo_address=info.appinfo[0] if info.appinfo else None,
                    appinfo_length=info.appinfo[1] if info.appinfo else None,
                    encrypted=info.encrypted,
                )
            ]
        )


class Cyacd2Handler(Handler):
    NAME = "cyacd2"
    # A 24-digit header line with file version 01, then an @ or data line.
    PATTERNS = [Regex(r"01[0-9A-Fa-f]{22}\r?\n[@:]")]
    EXTRACTOR = Cyacd2Extractor()
    DOC = HandlerDoc(
        name="Infineon .cyacd2",
        description="Infineon DFU SDK / PSoC 6 bootloader file: a header line, optional @APPINFO and @EIV lines and address-carrying data lines; data is written as one file per contiguous address range.",
        handler_type=HandlerType.ARCHIVE,
        vendor="Infineon (Cypress)",
        references=[
            Reference(
                title="Infineon: Device Firmware Update (DFU) Middleware Library, Appendix C (.cyacd2 format)",
                url="https://infineon.github.io/dfu/dfu_sdk_api_reference_manual/html/index.html",
            ),
            Reference(
                title="DefenseMouse/ohcya: .cyacd and .cyacd2 tools",
                url="https://github.com/DefenseMouse/ohcya",
            ),
        ],
        limitations=[
            "Encrypted (@EIV) files are written as stored, not decrypted",
        ],
    )

    def calculate_chunk(self, file: File, start_offset: int) -> ValidChunk | None:
        info = parse_cyacd2(file, start_offset, keep_data=False)
        return ValidChunk(start_offset=start_offset, end_offset=info.end)
