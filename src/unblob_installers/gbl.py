"""Silicon Labs Gecko Bootloader image, GBL v3 (FSD §13d).

A stream of tags: tag ID (u32 LE), length (u32 LE), data. The header tag
comes first and the end tag, holding a CRC-32, last; the CRC-32 of every tag
byte through the end tag is 0x2144DF1C. Program-data tags carry a flash
address (u32 LE) and data, raw (PROG, ERASEPROG), one raw LZ4 block, or the
.lzma "alone" form. Tag values as in Silicon Labs' btl_gbl_format.h.
"""

import lzma
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

import lz4.block
from unblob.file_utils import InvalidInputFormat
from unblob.models import (
    ExtractError,
    Extractor,
    ExtractResult,
    File,
    Handler,
    HandlerDoc,
    HandlerType,
    HexString,
    Reference,
    ValidChunk,
)
from unblob.report import ExtractionProblem, Report, UnknownError

from ._extract import require_whole_chunk
from ._regions import OverlapConflictError, assemble, region_name

HEADER_TAG = 0x03A617EB
END_TAG = 0xFC0404FC
VERSION_3 = b"\x00\x00\x00\x03"
PROG = 0xFE0101FE
ERASEPROG = 0xFD0303FD
PROG_LZ4 = 0xFD0505FD
PROG_LZMA = 0xFD0707FD
PROGRAM_DATA = (PROG, ERASEPROG, PROG_LZ4, PROG_LZMA)
TYPE_ENCRYPTED = 0x001
TYPE_SIGNED = 0x100
CRC_RESIDUE = 0x2144DF1C
TAG_HEADER = struct.Struct("<II")  # tag ID, length
# NFR-SEC-07: one LZ4 or LZMA tag decompresses to at most 16 MiB.
DECOMPRESSED_CAP = 16 * 1024 * 1024
_CRC_BLOCK = 1 << 20


class GblReport(Report):
    """An encrypted GBL, written as raw tags (FR-GBL-06)."""

    encrypted: bool
    signed: bool


@dataclass(frozen=True)
class Tag:
    index: int
    tag_id: int
    offset: int  # of the data, relative to the GBL start
    length: int


@dataclass(frozen=True)
class GblInfo:
    tags: list[Tag]  # header first, end tag last
    end: int  # after the end tag, relative
    header_type: int


def _crc_through(file: File, length: int, crc: int) -> int:
    """Continue crc over the next length bytes of file, a block at a time."""
    while length:
        block = file.read(min(length, _CRC_BLOCK))
        crc = zlib.crc32(block, crc)
        length -= len(block)
    return crc


def _read_tags(file: File, start: int, size: int) -> tuple[list[Tag], int, int]:
    """Tags from start through the end tag, the offset after it, and their CRC-32."""
    tags: list[Tag] = []
    pos = start
    crc = 0
    while not tags or tags[-1].tag_id != END_TAG:
        if pos + TAG_HEADER.size > size:
            raise InvalidInputFormat("tag header runs past the end of the input")
        file.seek(pos)
        head = file.read(TAG_HEADER.size)
        tag_id, length = TAG_HEADER.unpack(head)
        data = pos + TAG_HEADER.size
        if length > size - data:
            raise InvalidInputFormat("tag runs past the end of the input")
        if not tags and (tag_id, length) != (HEADER_TAG, 8):
            raise InvalidInputFormat("no GBL header tag")
        tags.append(Tag(len(tags), tag_id, data - start, length))
        crc = _crc_through(file, length, zlib.crc32(head, crc))
        pos = data + length
    return tags, pos, crc


def gbl_info(file: File, start: int, size: int) -> GblInfo:
    """Parse the GBL at start in an input of size bytes; InvalidInputFormat if not one."""
    tags, end, crc = _read_tags(file, start, size)
    file.seek(start + 8)
    header = file.read(8)
    if header[:4] != VERSION_3:
        raise InvalidInputFormat("not GBL version 3")
    if tags[-1].length != 4 or crc != CRC_RESIDUE:
        raise InvalidInputFormat("GBL CRC-32 mismatch")
    if len(tags) < 3:
        raise InvalidInputFormat("no tag between the GBL header and end tag")
    return GblInfo(
        tags=tags,
        end=end - start,
        header_type=struct.unpack("<I", header[4:])[0],
    )


def _decompress(tag_id: int, data: bytes) -> bytes:
    """Decompress one LZ4 or LZMA tag's data; ValueError when over the cap or corrupt."""
    if tag_id == PROG_LZ4:
        try:
            out = lz4.block.decompress(data, uncompressed_size=DECOMPRESSED_CAP + 1)
        except lz4.block.LZ4BlockError as exc:
            raise ValueError(
                f"LZ4 data does not decompress within the cap: {exc}"
            ) from None
    else:
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        try:
            out = decoder.decompress(data, max_length=DECOMPRESSED_CAP + 1)
        except lzma.LZMAError as exc:
            raise ValueError(f"LZMA data is corrupt: {exc}") from None
        if len(out) <= DECOMPRESSED_CAP and not decoder.eof:
            raise ValueError("LZMA stream is truncated")
    if len(out) > DECOMPRESSED_CAP:
        raise ValueError(f"decompresses to more than {DECOMPRESSED_CAP} bytes")
    return out


def _program_write(tag: Tag, body: bytes) -> tuple[int, bytes, int]:
    """(address, program data, tag index) of a program-data tag; ValueError if unusable."""
    if len(body) < 4:
        raise ValueError("has no address")
    address = struct.unpack_from("<I", body)[0]
    payload = body[4:]
    if tag.tag_id in (PROG_LZ4, PROG_LZMA):
        payload = _decompress(tag.tag_id, payload)
    return address, payload, tag.index


class GblExtractor(Extractor):
    def extract(self, inpath: Path, outdir: Path) -> ExtractResult | None:
        require_whole_chunk(GblHandler().calculate_chunk, inpath)
        data = inpath.read_bytes()
        info = gbl_info(File.from_bytes(data), 0, len(data))
        encrypted = bool(info.header_type & TYPE_ENCRYPTED)
        writes: list[tuple[int, bytes, int]] = []
        reports: list[Report] = []
        for tag in info.tags[1:-1]:
            body = data[tag.offset : tag.offset + tag.length]
            if encrypted or tag.tag_id not in PROGRAM_DATA:
                (outdir / f"tag_0x{tag.tag_id:08x}_{tag.index}.bin").write_bytes(body)
                continue
            try:
                writes.append(_program_write(tag, body))
            except ValueError as exc:  # NFR-SEC-07: the tag is left out
                reports.append(_problem(tag, str(exc)))
        try:
            regions = assemble(writes)
        except OverlapConflictError as exc:  # FR-GBL-08
            problem = f"GBL tags {exc.first} and {exc.second} write different bytes at 0x{exc.address:08x}"
            raise ExtractError(UnknownError(exception=ValueError(problem))) from None
        for address, payload in regions:
            (outdir / region_name(address)).write_bytes(payload)
        if encrypted:  # FR-GBL-06
            reports.append(
                GblReport(encrypted=True, signed=bool(info.header_type & TYPE_SIGNED))
            )
        return ExtractResult(reports=reports)


def _problem(tag: Tag, what: str) -> ExtractionProblem:
    return ExtractionProblem(
        problem=f"GBL tag {tag.index} (0x{tag.tag_id:08x}): {what}",
        resolution="Its program data was not written.",
    )


class GblHandler(Handler):
    NAME = "gbl"
    PATTERNS = [
        HexString("EB 17 A6 03 08 00 00 00 00 00 00 03")
    ]  # header tag ID, length 8, version 3
    EXTRACTOR = GblExtractor()
    DOC = HandlerDoc(
        name="Silicon Labs GBL",
        description="Gecko Bootloader upgrade image, version 3: a stream of tags whose program data is written as one file per contiguous address range; other tags are written as stored.",
        handler_type=HandlerType.ARCHIVE,
        vendor="Silicon Labs",
        references=[
            Reference(
                title="UG266/UG489: Silicon Labs Gecko Bootloader User's Guide (GBL file format)",
                url="https://www.silabs.com/documents/public/user-guides/ug489-gecko-bootloader-user-guide-gsdk-4.pdf",
            ),
            Reference(
                title="zigpy/pygbl: GBL parser and builder",
                url="https://github.com/zigpy/pygbl",
            ),
        ],
        limitations=[
            "Encrypted images are not decrypted; their tags are written as stored",
            "Signatures and certificates are written as stored, not verified",
            "GBL v4 and EBL are not supported",
        ],
    )

    def calculate_chunk(self, file: File, start_offset: int) -> ValidChunk | None:
        file.seek(0, 2)
        size = file.tell()
        info = gbl_info(file, start_offset, size)
        end = start_offset + info.end
        file.seek(end)
        padding = file.read(min((-info.end) % 4, size - end))
        end += len(padding) - len(padding.lstrip(b"\xff"))  # FR-GBL-03
        return ValidChunk(start_offset=start_offset, end_offset=end)
