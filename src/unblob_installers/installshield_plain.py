"""InstallShield single-file setup.exe, ISx's unencrypted "plain" layouts (FSD §13a).

The records follow the PE image directly, with no header. ANSI plain: per
file four NUL-terminated strings (source name, destination name, version,
data length in decimal), then the data. UTF-16 plain: a file count (u32 LE),
then per file the same four strings in UTF-16LE, then the data. Format facts
as lifenjoiner/ISx (MIT) `extract_plain_files` and `extract_plain_files_w`
read them; written from FSD §13a.1, not from ISx's code.
"""

import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from unblob.file_utils import File, FileSystem, InvalidInputFormat
from unblob.models import (
    Extractor,
    ExtractResult,
    Handler,
    HandlerDoc,
    HandlerType,
    HexString,
    Reference,
    ValidChunk,
)
from unblob.report import ExtractionProblem

from ._extract import require_whole_chunk
from ._pe import certificate_table, image_end

# Bytes allowed in an ANSI string, and the UTF-16 code unit range (§13a.1)
_ANSI = bytes(range(0x20, 0xFF))
MAX_DIGITS = 10
MAX_COUNT = 65535
# The certificate table starts at the next 8-byte boundary after the package
# (FR-ISW-09): at most 7 zero bytes lie between.
MAX_ALIGNMENT = 7


@dataclass(frozen=True)
class Record:
    destination: str
    data_offset: int  # file offset
    length: int


def _ansi_string(buf, pos: int, limit: int) -> tuple[bytes, int] | None:
    """Parse a NUL-terminated string of 1+ bytes in 0x20-0xFE before limit.

    Returns the string and the offset after its NUL, or None.
    """
    end = buf.find(b"\0", pos, limit)
    if end <= pos:
        return None
    text = bytes(buf[pos:end])
    if text.translate(None, _ANSI):  # a byte outside 0x20-0xFE
        return None
    return text, end + 1


def _utf16_string(buf, pos: int, limit: int) -> tuple[str, int] | None:
    """Parse a UTF-16LE string of 1+ characters in 0x0020-0xFFFD ending in a 2-byte NUL."""
    end = buf.find(b"\0\0", pos, limit)
    while end != -1 and (end - pos) % 2:  # a NUL pair across two characters
        end = buf.find(b"\0\0", end + 1, limit)
    if end <= pos:
        return None
    raw = bytes(buf[pos:end])
    units = memoryview(raw).cast("H")  # little-endian host (x86, arm64)
    if min(units) < 0x20 or max(units) > 0xFFFD:
        return None
    return raw.decode("utf-16-le", errors="surrogatepass"), end + 2


def _length(text: str) -> int | None:
    if not 1 <= len(text) <= MAX_DIGITS or not text.isascii() or not text.isdigit():
        return None
    return int(text)


def _ansi_record(buf, pos: int, limit: int) -> tuple[str, int, int] | None:
    """(destination, data offset, data length) if four strings parse at pos."""
    fields = []
    for _ in range(4):
        parsed = _ansi_string(buf, pos, limit)
        if parsed is None:
            return None
        text, pos = parsed
        fields.append(text.decode("latin-1"))
    length = _length(fields[3])
    return None if length is None else (fields[1], pos, length)


def _utf16_record(buf, pos: int, limit: int) -> tuple[str, int, int] | None:
    fields = []
    for _ in range(4):
        parsed = _utf16_string(buf, pos, limit)
        if parsed is None:
            return None
        text, pos = parsed
        fields.append(text)
    length = _length(fields[3])
    return None if length is None else (fields[1], pos, length)


def _is_utf16(buf, overlay: int, limit: int) -> bool:
    if overlay + 6 > limit:
        return False
    (count,) = struct.unpack("<I", buf[overlay : overlay + 4])
    return 1 <= count <= MAX_COUNT and buf[overlay + 5 : overlay + 6] == b"\0"


def plain_records(buf, start: int, size: int) -> tuple[list[Record], int]:
    """Return the records of the plain package after the PE at start, and its end (FR-ISW-07/08)."""
    overlay = start + image_end(buf, start)
    cert_offset, cert_size = certificate_table(buf, start)
    limit = (
        start + cert_offset if cert_size and start + cert_offset >= overlay else size
    )
    if overlay >= limit:
        raise InvalidInputFormat("PE without an overlay")
    records: list[Record] = []
    if _is_utf16(buf, overlay, limit):
        (count,) = struct.unpack("<I", buf[overlay : overlay + 4])
        pos = overlay + 4
        for _ in range(count):
            parsed = _utf16_record(buf, pos, limit)
            if parsed is None:
                raise InvalidInputFormat("UTF-16 plain record does not parse")
            pos = _take(records, parsed, limit)
        return records, pos
    pos = overlay
    while pos < limit:
        parsed = _ansi_record(buf, pos, limit)
        if parsed is None:
            break  # the package ends here (FR-ISW-09)
        pos = _take(records, parsed, limit)
    if not records:
        raise InvalidInputFormat("no ANSI plain record at the overlay")
    return records, pos


def _take(records: list[Record], parsed: tuple[str, int, int], limit: int) -> int:
    destination, data_offset, length = parsed
    if data_offset + length > limit:
        raise InvalidInputFormat("plain record data runs past the overlay")
    records.append(Record(destination, data_offset, length))
    return data_offset + length


def chunk_end(buf, start: int, size: int) -> int:
    """End of the chunk: the last record's data, or the certificate table (FR-ISW-09)."""
    _, end = plain_records(buf, start, size)
    cert_offset, cert_size = certificate_table(buf, start)
    gap = start + cert_offset - end
    if (
        cert_size
        and 0 <= gap <= MAX_ALIGNMENT
        and start + cert_offset + cert_size <= size
        and not any(buf[end : start + cert_offset])
    ):
        return start + cert_offset + cert_size
    return end


def member_path(name: str) -> PurePosixPath | None:
    """Return the destination as a relative path; None for a name NFR-SEC-08 rejects."""
    path = name.replace("\\", "/")
    if path.startswith("/") or (len(path) >= 2 and path[1] == ":"):
        return None
    if ".." in path.split("/"):
        return None
    return PurePosixPath(path)


class InstallShieldPlainExtractor(Extractor):
    def extract(self, inpath: Path, outdir: Path) -> ExtractResult | None:
        require_whole_chunk(InstallShieldPlainHandler().calculate_chunk, inpath)
        fs = FileSystem(outdir)
        with File.from_path(inpath) as file:
            records, _ = plain_records(file, 0, file.size())
            for record in records:
                path = member_path(record.destination)
                if path is None:  # NFR-SEC-08
                    fs.record_problem(
                        ExtractionProblem(
                            problem=f"member name {record.destination!r} points outside the extraction directory",
                            resolution="Skipped",
                        )
                    )
                    continue
                fs.carve(Path(path), file, record.data_offset, record.length)
        return ExtractResult(reports=fs.problems)


class InstallShieldPlainHandler(Handler):
    NAME = "installshield_plain"
    # "MZ", the DOS header up to e_lfanew, whose two upper bytes are zero
    PATTERNS = [HexString("4d 5a [58] ?? ?? 00 00")]
    EXTRACTOR = InstallShieldPlainExtractor()
    DOC = HandlerDoc(
        name="InstallShield single-file setup.exe (plain layouts)",
        description="InstallShield setup.exe whose files follow the PE image unencrypted, with no package header: ANSI records of four strings, or a file count and UTF-16 records; each file is written under its destination name.",
        handler_type=HandlerType.EXECUTABLE,
        vendor="Flexera (InstallShield)",
        references=[
            Reference(
                title="ISx InstallShield installer extractor (plain layouts)",
                url="https://github.com/lifenjoiner/ISx",
            ),
        ],
        limitations=[
            "Headered packages (InstallShield or ISSetupStream signature) are left to installshield_setup",
        ],
    )

    def calculate_chunk(self, file: File, start_offset: int) -> ValidChunk | None:
        end = chunk_end(file, start_offset, file.size())
        return ValidChunk(start_offset=start_offset, end_offset=end)
