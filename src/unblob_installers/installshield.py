"""InstallShield cabinet handler (FSD §6).

Format: as read by unshield (https://github.com/twogood/unshield, MIT): a
common header, a cabinet descriptor with a file table, and file data. Only
the version 5 layout (header version 0x01xxxxxx, major 0 or 5) is handled.
"""

import shutil
import struct
import subprocess
import tempfile
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

COMMON = struct.Struct(
    "<4sIIII"
)  # signature, version, volume info, descriptor offset, size
VOLUME_V5 = struct.Struct(
    "<10I"
)  # data offset, unknown, first/last index, first/last file
FILE_INVALID = 0x8
FD_FLAGS, FD_SIZES, FD_DATA_OFFSET = 8, 10, 0x26  # within a v5 file descriptor


def _unpack(fmt: str | struct.Struct, buf, offset: int) -> tuple:
    layout = fmt if isinstance(fmt, struct.Struct) else struct.Struct(fmt)
    if offset < 0 or offset + layout.size > len(buf):
        raise InvalidInputFormat(
            "InstallShield structure runs past the end of the data"
        )
    return layout.unpack_from(buf, offset)


def major_version(version: int) -> int:
    """Major format version, as unshield derives it (minimum 5)."""
    if version >> 24 == 1:
        major = (version >> 12) & 0xF
    elif version >> 24 in (2, 4):
        major = (version & 0xFFFF) // 100
    else:
        raise InvalidInputFormat(
            f"unknown InstallShield header version 0x{version:08x}"
        )
    return max(major, 5)


def _file_table_end(buf, start: int, descriptor: int) -> int:
    """Furthest data offset + compressed size over the v5 file table."""
    (table_offset,) = _unpack("<I", buf, descriptor + 0x0C)
    (directories,) = _unpack("<I", buf, descriptor + 0x1C)
    (files,) = _unpack("<I", buf, descriptor + 0x28)
    table = descriptor + table_offset
    offsets = _unpack(f"<{directories + files}I", buf, table)
    end = 0
    for entry in offsets[directories:]:
        fd = table + entry
        (flags,) = _unpack("<H", buf, fd + FD_FLAGS)
        _expanded, compressed = _unpack("<II", buf, fd + FD_SIZES)
        (data_offset,) = _unpack("<I", buf, fd + FD_DATA_OFFSET)
        if flags & FILE_INVALID or not data_offset:
            continue
        end = max(end, start + data_offset + compressed)
    return end


def cabinet_end(buf, start: int) -> int:
    """End offset of the self-contained cabinet at start (FR-ISC-02)."""
    signature, version, _info, desc_offset, desc_size = _unpack(COMMON, buf, start)
    if signature != b"ISc(":
        raise InvalidInputFormat("no ISc( signature")
    if major_version(version) != 5:
        raise InvalidInputFormat("only the version 5 cabinet layout is handled")
    if desc_size == 0:
        raise InvalidInputFormat("continuation volume without a descriptor")
    end = start + desc_offset + desc_size
    volume = _unpack(VOLUME_V5, buf, start + COMMON.size)
    last_offset, last_compressed = volume[7], volume[9]
    if last_offset:  # a spanned volume records where its data ends
        end = max(end, start + last_offset + last_compressed)
    else:
        end = max(end, _file_table_end(buf, start, start + desc_offset))
    if end > len(buf):
        raise InvalidInputFormat("file data lies beyond the data (a multi-volume set)")
    return end


class UnshieldExtractor(Extractor):
    def get_dependencies(self) -> list[str]:
        return ["unshield"]

    def extract(self, inpath: Path, outdir: Path) -> ExtractResult | None:
        # unshield derives sibling volume names from "data1.cab".
        with tempfile.TemporaryDirectory() as tmp:
            cab = Path(tmp) / "data1.cab"
            shutil.copyfile(inpath, cab)
            command = ["unshield", "-d", str(outdir), "x", str(cab)]
            result = subprocess.run(command, capture_output=True, check=False)
        if result.returncode != 0:
            raise ExtractError(
                ExtractCommandFailedReport(
                    command=" ".join(command),
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode,
                )
            )
        return ExtractResult(reports=[])


class InstallShieldHandler(Handler):
    NAME = "installshield"
    PATTERNS = [HexString("49 53 63 28")]  # "ISc("
    EXTRACTOR = UnshieldExtractor()
    DOC = HandlerDoc(
        name="InstallShield cabinet",
        description="InstallShield cabinet (data1.cab) holding an installer's files, extracted with unshield.",
        handler_type=HandlerType.ARCHIVE,
        vendor="Flexera (InstallShield)",
        references=[
            Reference(title="unshield", url="https://github.com/twogood/unshield"),
            Reference(
                title="InstallScript .cab and .hdr files",
                url="https://docs.revenera.com/installshield/helplibrary/IsCabViewOverview.htm",
            ),
        ],
        limitations=[
            "Only the version 5 cabinet layout",
            "Multi-volume sets (data1.hdr + dataN.cab, or spanned dataN.cab) are not handled",
        ],
    )

    def calculate_chunk(self, file: File, start_offset: int) -> ValidChunk | None:
        return ValidChunk(
            start_offset=start_offset, end_offset=cabinet_end(file, start_offset)
        )
