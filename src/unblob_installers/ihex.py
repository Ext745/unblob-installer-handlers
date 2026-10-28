"""Intel HEX handler (FSD §11).

Format: Intel Hexadecimal Object File Format Specification, rev. A (1988).
Records are `:` · count · address · type · data · checksum, one per line.
"""

import binascii
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from unblob.file_utils import InvalidInputFormat
from unblob.models import (
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
from unblob.report import ExtractionProblem

from ._extract import require_whole_chunk
from ._regions import OverlapConflictError, assemble, region_name

DATA, EOF, EXT_SEGMENT, START_SEGMENT, EXT_LINEAR, START_LINEAR = range(6)
# ':' + 2 hex chars per byte of count, address (2), type, up to 255 data, checksum.
MAX_LINE = 1 + 2 * (1 + 2 + 1 + 255 + 1)

__all__ = ["chunk_end", "region_name"]


@dataclass(frozen=True)
class Record:
    type: int
    address: int
    data: bytes


def parse_record(line: bytes) -> Record | None:
    """Return the record on one line (terminator removed), or None if invalid."""
    if not line.startswith(b":") or len(line) % 2 != 1 or len(line) < 11:
        return None
    try:
        raw = binascii.unhexlify(line[1:])
    except binascii.Error:
        return None
    count, address, rtype = raw[0], int.from_bytes(raw[1:3], "big"), raw[3]
    if len(raw) != count + 5 or rtype > START_LINEAR or sum(raw) & 0xFF:
        return None
    return Record(type=rtype, address=address, data=raw[4:-1])


class _Buffer(Protocol):
    def __len__(self) -> int: ...
    def __getitem__(self, key: slice, /) -> bytes: ...
    def find(self, sub: bytes, start: int, end: int, /) -> int: ...


def _chunk_length(buf: _Buffer, start: int) -> int | None:
    """Length of the valid record run from start through its EOF line, or None.

    Reads at most one maximum-length record per line, so a huge text without
    newlines is never read whole.
    """
    pos = start
    data_records = 0
    while pos < len(buf):
        newline = buf.find(b"\n", pos, pos + MAX_LINE + 2)
        end = newline + 1 if newline != -1 else min(len(buf), pos + MAX_LINE + 2)
        line = buf[pos:end]
        if newline == -1 and end < len(buf):
            return None  # longer than any record
        record = parse_record(line.rstrip(b"\r\n"))
        if record is None:
            return None
        pos = end
        if record.type == DATA:
            data_records += 1
        elif record.type == EOF:
            return pos - start if data_records else None
    return None


def chunk_end(data: bytes, start: int) -> int | None:
    """End offset of the Intel HEX chunk starting at start, or None (FR-HEX-01..03)."""
    length = _chunk_length(data, start)
    return None if length is None else start + length


def _next_base(record: Record, base: int) -> int:
    if record.type == EXT_SEGMENT:
        return int.from_bytes(record.data, "big") << 4
    if record.type == EXT_LINEAR:
        return int.from_bytes(record.data, "big") << 16
    return base


def data_writes(text: bytes) -> list[tuple[int, bytes, int]]:
    """(absolute address, data, line number) of every data record up to EOF."""
    writes: list[tuple[int, bytes, int]] = []
    base = 0
    for line_no, line in enumerate(text.splitlines(), start=1):
        record = parse_record(line)
        if record is None:
            continue
        if record.type == EOF:
            break
        if record.type == DATA:
            writes.append(((base + record.address) & 0xFFFFFFFF, record.data, line_no))
        base = _next_base(record, base)
    return writes


class IntelHexExtractor(Extractor):
    def extract(self, inpath: Path, outdir: Path) -> ExtractResult | None:
        require_whole_chunk(IntelHexHandler().calculate_chunk, inpath)
        writes = data_writes(inpath.read_bytes())
        try:
            regions = assemble(writes)
        except OverlapConflictError as exc:
            return ExtractResult(
                reports=[
                    ExtractionProblem(
                        path=str(inpath),
                        problem=f"Intel HEX lines {exc.first} and {exc.second} write different bytes at 0x{exc.address:08x}",
                        resolution="not extracted",
                    )
                ]
            )
        for address, data in regions:
            (outdir / region_name(address)).write_bytes(data)
        return ExtractResult(reports=[])


class IntelHexHandler(Handler):
    NAME = "ihex"
    # A record header at the start of a line: ':' count(2) address(4) type 00-05.
    PATTERNS = [Regex(r"(^|\n):[0-9A-Fa-f]{6}0[0-5]")]
    EXTRACTOR = IntelHexExtractor()
    DOC = HandlerDoc(
        name="Intel HEX",
        description="Intel Hexadecimal Object File: text records with addresses and checksums, used by Arduino/AVR, STM32, CH32 and most embedded IDEs.",
        handler_type=HandlerType.ARCHIVE,
        vendor="Intel",
        references=[
            Reference(
                title="Intel Hexadecimal Object File Format Specification, rev. A",
                url="https://archive.org/details/IntelHEXStandard",
            ),
            Reference(
                title="Intel HEX (Wikipedia)",
                url="https://en.wikipedia.org/wiki/Intel_HEX",
            ),
        ],
        limitations=[
            "One file per contiguous address region; gaps are not padded",
            "Start-address records (types 03 and 05) are not reported",
        ],
    )

    def calculate_chunk(self, file: File, start_offset: int) -> ValidChunk | None:
        # The pattern may match the newline before the colon.
        file.seek(start_offset)
        if file.read(1) == b"\n":
            start_offset += 1
        length = _chunk_length(file, start_offset)
        if length is None:
            raise InvalidInputFormat("not a complete, valid Intel HEX record run")
        return ValidChunk(start_offset=start_offset, end_offset=start_offset + length)
