"""Setup Factory handler (FSD §8), for Setup Factory 7 to 10.

The overlay after the PE's last section opens with a signature, then holds
irsetup.exe, optionally lua5.1.dll, and a table of named files that includes
the compressed script irsetup.dat. The installed files follow the table; only
the script's CSetupFileData entries give their sizes, so the chunk end is
found by decompressing the script and summing them. The layout follows
sfextract's setupfactory8.py (MIT) with this project's Setup Factory 10
patch, and for Setup Factory 7 sfextract's setupfactory7.py (MIT): a shorter
signature, an XOR-ed irsetup.exe, 32-bit sizes. Extraction runs sfextract.
"""

import lzma
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

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
from unblob.report import ExtractCommandFailedReport

from . import _blast
from ._extract import run_tool
from ._pe import certificate_end, overlay_start

SIGNATURE = bytes.fromhex("e0e0e1e1e2e2e3e3e4e4e5e5e6e6e7e7")
HEADER_SIZE = 26  # signature and 10 bytes nobody has decoded
NAME_SIZE = 264
SIGNATURE_7 = bytes.fromhex("e0e1e2e3e4e5e6e7")
NAME_SIZE_7 = 260
XORED_MZ = bytes(b ^ 0x07 for b in b"MZ")  # SF7 XORs irsetup.exe's start with 0x07
LUA_DLL_HINT = 1000  # a file count above this is lua5.1.dll's size instead
SCRIPT_NAME = b"irsetup.dat"
SCRIPT_LIMIT = 64 * 1024 * 1024  # decompressed script; the sample's is 132 KiB
SCRIPT_STEP = 1024 * 1024
DECODER_LIMIT = (
    SCRIPT_LIMIT + 1024 * 1024
)  # a dictionary up to the script cap (NFR-SEC-05)
VERSION_INFO = struct.pack("<I", 0xFEEF04BD)  # VS_FIXEDFILEINFO signature
SUPPORTED_MAJORS = (7, 8, 9, 10)


class _Cursor:
    def __init__(self, buf, pos: int, end: int):
        self.buf, self.pos, self.end = buf, pos, end

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > self.end:
            raise InvalidInputFormat("Setup Factory data runs past its end")
        data = bytes(self.buf[self.pos : self.pos + n])
        self.pos += n
        return data

    def skip(self, n: int) -> None:
        self.take(n)

    def unpack(self, fmt: str) -> int:
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self) -> bytes:
        return self.take(self.unpack("<B"))


def runtime_version(buf, start: int, end: int) -> tuple[int, int]:
    """FileVersion (major, minor) from the run-time's VS_FIXEDFILEINFO."""
    at = bytes(buf[start:end]).find(VERSION_INFO)
    if at == -1:
        raise InvalidInputFormat("no version information")
    (version_ms,) = struct.unpack_from("<I", buf, start + at + 8)
    return version_ms >> 16, version_ms & 0xFFFF


def _lzma_capped(d: lzma.LZMADecompressor, data: bytes) -> bytearray:
    """Decompress in steps, declining once the script passes SCRIPT_LIMIT (NFR-SEC-04).

    One call with max_length would hold the output twice while lzma joins its
    blocks; steps into one buffer hold the script once.
    """
    script = bytearray()
    step = d.decompress(data, max_length=SCRIPT_STEP)
    while True:
        # Checked before appending, so the buffer never grows past the limit.
        if len(script) + len(step) > SCRIPT_LIMIT:
            raise InvalidInputFormat("Setup Factory script is over the 64 MiB limit")
        script += step
        if d.eof or d.needs_input:
            return script
        step = d.decompress(b"", max_length=SCRIPT_STEP)


def decompress(data: bytes) -> bytes | bytearray:
    """Decompress a table file, detecting the method as sfextract does."""
    try:
        if data[:2] == b"\x00\x06":
            return _blast.decompress(data, SCRIPT_LIMIT)
        if data[:2] == b"\x5d\x00":
            # The header chooses the dictionary: bound it before it is allocated.
            d = lzma.LZMADecompressor(lzma.FORMAT_ALONE, memlimit=DECODER_LIMIT)
            return _lzma_capped(d, data)
        if data[:1] == b"\x18":
            # One LZMA2 dictionary-size byte, then the 8-byte unpacked size.
            dict_size = (2 | data[0] & 1) << (data[0] // 2 + 11)
            lzma2 = {"id": lzma.FILTER_LZMA2, "dict_size": dict_size}
            d = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[lzma2])
            return _lzma_capped(d, data[9:])
    except (lzma.LZMAError, ValueError) as e:
        raise InvalidInputFormat(
            f"Setup Factory script does not decompress: {e}"
        ) from e
    raise InvalidInputFormat("unknown Setup Factory compression")


@dataclass(frozen=True)
class _Layout:
    """Where one CSetupFileData entry's fields sit, by Setup Factory version."""

    before_dest: int  # sizes, attributes and timestamps before the destination
    after_dest: int
    size_format: str  # the compressed size
    trailer: int


def _layout(version: tuple[int, int]) -> _Layout:
    if version >= (10, 0):
        return _Layout(72, 12, "<q", 3)
    if version >= (9, 2):  # sfextract says 9.3; a 9.2.0.0 installer has it too
        return _Layout(72, 11, "<q", 8)
    if version >= (8, 0):
        return _Layout(72, 10, "<q", 8)
    return _Layout(44, 10, "<I", 8)


def _entry_size(c: _Cursor, layout: _Layout) -> int:
    """Read one CSetupFileData entry; its compressed size."""
    for _ in range(6):  # source path, base name, directory, suffix, folder, description
        c.string()
    c.skip(layout.before_dest)
    c.string()  # destination directory
    c.skip(layout.after_dest)
    for _ in range(5):  # shortcut location, comment, description, arguments, start dir
        c.string()
    c.skip(1)
    c.string()  # icon path
    c.skip(8)
    c.string()  # font name
    c.skip(16)  # compression and attribute flags
    c.skip(2 * c.unpack("<H"))
    c.string()  # condition
    c.skip(2)
    c.string()  # install type
    c.string()
    for _ in range(c.unpack("<H")):
        c.string()  # package names
    c.string()  # notes
    size = c.unpack(layout.size_format)
    if size < 0:
        raise InvalidInputFormat("negative Setup Factory file size")
    c.skip(4 + layout.trailer)  # CRC and trailer
    return size


def entries_size(script: bytes | bytearray, version: tuple[int, int]) -> int:
    """Sum of the compressed sizes of the script's CSetupFileData entries."""
    at = script.find(b"CSetupFileData")
    if at < 8:  # count and class header precede the name
        raise InvalidInputFormat("no CSetupFileData in the script")
    c = _Cursor(script, at - 8, len(script))
    count = c.unpack("<H")
    c.skip(4)  # 0xFFFF, 0x0001: a new MFC class follows
    if c.take(c.unpack("<H")) != b"CSetupFileData":
        raise InvalidInputFormat("malformed CSetupFileData header")
    c.skip(5)
    layout = _layout(version)
    return sum(_entry_size(c, layout) for _ in range(count))


# MFC class headers: 0xFFFF, schema 1, name length, name.
DEPENDENCY_CLASS = b"\xff\xff\x01\x00\x10\x00CSetupDependency"
DEPENDENCY_FILE_CLASS = b"\xff\xff\x01\x00\x0f\x00CDependencyFile"


def dependency_size(script: bytes | bytearray) -> int:
    """Return the stored size of the dependency modules' files, 0 if none.

    A dependency module (the VB6 run-time, say) keeps its files ahead of the
    archive files. Decoded from one Setup Factory 8.1 installer with one
    module holding one stored file, whose two sizes are equal, so which of
    them is the stored size is unproven; any other shape is declined.
    """
    at = script.find(DEPENDENCY_CLASS)
    if at == -1:
        return 0
    if at < 2 or struct.unpack_from("<H", script, at - 2)[0] != 1:
        raise InvalidInputFormat("several Setup Factory dependency modules")
    at = script.find(DEPENDENCY_FILE_CLASS, at)
    if at < 2:
        raise InvalidInputFormat("Setup Factory dependency module without files")
    c = _Cursor(script, at - 2, len(script))
    if c.unpack("<H") != 1:
        raise InvalidInputFormat("Setup Factory dependency module with several files")
    c.skip(len(DEPENDENCY_FILE_CLASS) + 4)
    c.string()  # source path
    c.skip(8)  # the first size
    size = c.unpack("<q")
    if size < 0:
        raise InvalidInputFormat("negative Setup Factory dependency file size")
    return size


def _file_count(c: _Cursor) -> int:
    """Skip irsetup.exe and lua5.1.dll if present; the table's file count."""
    c.skip(c.unpack("<q"))  # irsetup.exe
    count = c.unpack("<I")
    if count > LUA_DLL_HINT:
        c.pos -= 4
        c.skip(c.unpack("<q"))  # lua5.1.dll
        count = c.unpack("<I")
    if count > LUA_DLL_HINT:
        raise InvalidInputFormat("implausible Setup Factory file count")
    return count


def _read_script(c: _Cursor, count: int, version: tuple[int, int]) -> bytes | bytearray:
    """Walk the file table to its end; the decompressed script."""
    script = None
    for _ in range(count):
        if version[0] == 7:  # 32-bit sizes, files always PKWARE-imploded
            name = c.take(NAME_SIZE_7).split(b"\0", 1)[0]
            size = c.unpack("<I")
            crc = c.unpack("<I")
        else:
            name = c.take(NAME_SIZE).split(b"\0", 1)[0]
            size = c.unpack("<q")
            crc = c.unpack("<I")
            c.skip(4)
        data = c.take(size)
        if name == SCRIPT_NAME:
            script = _blast_script(data) if version[0] == 7 else decompress(data)
            if crc and zlib.crc32(script) != crc:
                raise InvalidInputFormat("Setup Factory script CRC mismatch")
    if script is None:
        raise InvalidInputFormat("no Setup Factory script")
    return script


def _blast_script(data: bytes) -> bytearray:
    try:
        return _blast.decompress(data, SCRIPT_LIMIT)
    except ValueError as e:
        raise InvalidInputFormat(
            f"Setup Factory script does not decompress: {e}"
        ) from e


def _sf7_table(file: File, overlay: int) -> _Cursor:
    """Cursor at SF7's irsetup.exe size field.

    It follows the signature directly in 7.0.1 and 7.0.3 and one byte later
    in 7.0.6; the XOR-ed "MZ" after it shows which.
    """
    for shift in (0, 1):
        at = overlay + len(SIGNATURE_7) + shift
        if bytes(file[at + 4 : at + 6]) == XORED_MZ:
            return _Cursor(file, at, len(file))
    raise InvalidInputFormat("no Setup Factory 7 run-time after the signature")


def _sf7_file_count(c: _Cursor) -> int:
    c.skip(c.unpack("<I"))  # irsetup.exe
    count = c.unpack("<I")
    if count > LUA_DLL_HINT:
        raise InvalidInputFormat("implausible Setup Factory file count")
    return count


def data_end(file: File, start: int) -> int:
    """End of the last installed file's data in the installer at start."""
    overlay = overlay_start(file, start)
    if bytes(file[overlay : overlay + len(SIGNATURE)]) == SIGNATURE:
        c = _Cursor(file, overlay + HEADER_SIZE, len(file))
        majors = SUPPORTED_MAJORS[1:]
    elif bytes(file[overlay : overlay + len(SIGNATURE_7)]) == SIGNATURE_7:
        c = _sf7_table(file, overlay)
        majors = (7,)
    else:
        raise InvalidInputFormat("no Setup Factory overlay signature")
    version = runtime_version(file, start, overlay)
    if version[0] not in majors:
        raise InvalidInputFormat(f"Setup Factory {version[0]} is not supported")

    count = _sf7_file_count(c) if version[0] == 7 else _file_count(c)
    script = _read_script(c, count, version)
    end = c.pos + dependency_size(script) + entries_size(script, version)
    if end > len(file):
        raise InvalidInputFormat("Setup Factory data runs past the end of the data")
    return end


class SetupFactoryExtractor(Extractor):
    def get_dependencies(self) -> list[str]:
        return ["sfextract"]

    def extract(self, inpath: Path, outdir: Path) -> ExtractResult | None:
        command = ["sfextract", "-o", str(outdir), str(inpath)]
        result = run_tool(command)
        # sfextract exits 0 when it finds no extractor (FR-SF-03).
        if result.returncode != 0 or not result.stdout.startswith(b"Extracted "):
            raise ExtractError(
                ExtractCommandFailedReport(
                    command=" ".join(command),
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode,
                )
            )
        return ExtractResult(reports=[])


class SetupFactoryHandler(Handler):
    NAME = "setup_factory"
    PATTERNS = [HexString("4D 5A")]  # every PE; the overlay signature decides
    EXTRACTOR = SetupFactoryExtractor()
    DOC = HandlerDoc(
        name="Setup Factory",
        description="Setup Factory installer: a PE run-time with an overlay of the setup files and a script listing the installed files, extracted with sfextract.",
        handler_type=HandlerType.EXECUTABLE,
        vendor="Indigo Rose Software",
        references=[
            Reference(
                title="Setup Factory",
                url="https://www.indigorose.com/setup-factory/",
            ),
            Reference(
                title="sfextract",
                url="https://github.com/CybercentreCanada/sfextract",
            ),
        ],
        limitations=[
            "Setup Factory 6 and older are not recognised",
            "Installers with more than one dependency module, or a module with more than one file, are declined",
        ],
    )

    def calculate_chunk(self, file: File, start_offset: int) -> ValidChunk | None:
        cert_end = certificate_end(file, start_offset)  # also proves a PE starts here
        end = max(data_end(file, start_offset), cert_end)
        if end > len(file):
            raise InvalidInputFormat("certificate table runs past the end of the data")
        return ValidChunk(start_offset=start_offset, end_offset=end)
