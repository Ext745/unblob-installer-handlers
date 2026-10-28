"""Inno Setup handler (FSD §7).

The setup loader carries an offset table (layouts as innoextract's
src/loader/offsets.cpp reads them); its TotalSize is the installer's size
before signing. Extraction runs innoextract.
"""

import shutil
import struct
import tempfile
import zlib
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

from ._extract import run_tool
from ._pe import certificate_end

# Offset-table IDs and the earliest Inno version using each.
TABLE_IDS = {
    b"rDlPtS02\x87eVx": (1, 2, 10),
    b"rDlPtS04\x87eVx": (4, 0, 0),
    b"rDlPtS05\x87eVx": (4, 0, 3),
    b"rDlPtS06\x87eVx": (4, 0, 10),
    b"rDlPtS07\x87eVx": (4, 1, 6),
    b"rDlPtS\xcd\xe6\xd7{\x0b*": (5, 1, 5),
    b"nS5W7dT\x83\xaa\x1b\x0fj": (5, 1, 5),
}
# Revision 1 (5.1.5 to 6.4): TotalSize, OffsetEXE, UncompressedEXE, CRCEXE, Offset0, Offset1.
REV1 = struct.Struct("<6I")
# Revision 2 (6.5+): the same fields widened to Int64 where they are offsets or sizes.
REV2 = struct.Struct("<qqIIqqI")
SEARCH_LIMIT = 16 * 1024 * 1024  # the table lives in the loader's resources


def _table_total_size(buf, at: int, since: tuple[int, int, int]) -> int | None:
    """TotalSize from the table at `at`, or None if its CRC does not match."""
    if since < (5, 1, 5):
        return None  # pre-5.1.5 tables: no installer in the store uses them
    pos = at + 12
    if pos + 4 > len(buf):
        return None
    (revision,) = struct.unpack_from("<I", buf, pos)
    layout = REV2 if revision == 2 else REV1
    end = pos + 4 + layout.size
    if end + 4 > len(buf):
        return None
    (crc,) = struct.unpack_from("<I", buf, end)
    if zlib.crc32(bytes(buf[at:end])) != crc:
        return None
    return layout.unpack_from(buf, pos + 4)[0]


def total_size(buf, start: int) -> int:
    """TotalSize of the Inno setup at start; InvalidInputFormat if it is not one."""
    window = bytes(buf[start : start + SEARCH_LIMIT])
    for table_id, since in TABLE_IDS.items():
        at = window.find(table_id)
        while at != -1:
            size = _table_total_size(buf, start + at, since)
            if size:
                return size
            at = window.find(table_id, at + 1)
    raise InvalidInputFormat("no Inno Setup offset table")


class InnoExtractor(Extractor):
    def get_dependencies(self) -> list[str]:
        return ["innoextract"]

    def extract(self, inpath: Path, outdir: Path) -> ExtractResult | None:
        with tempfile.TemporaryDirectory() as tmp:
            setup = Path(tmp) / "setup.exe"
            shutil.copyfile(inpath, setup)
            command = ["innoextract", "-e", "-s", "-d", str(outdir), str(setup)]
            result = run_tool(command)
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


class InnoSetupHandler(Handler):
    NAME = "inno"
    PATTERNS = [HexString("4D 5A")]  # every PE; the offset table decides
    EXTRACTOR = InnoExtractor()
    DOC = HandlerDoc(
        name="Inno Setup",
        description="Inno Setup installer: a PE setup loader whose offset table locates the compressed setup data, extracted with innoextract.",
        handler_type=HandlerType.EXECUTABLE,
        vendor="Jordan Russell / JR Software",
        references=[
            Reference(title="Inno Setup", url="https://jrsoftware.org/isinfo.php"),
            Reference(title="innoextract", url="https://constexpr.org/innoextract/"),
        ],
        limitations=["Installers older than Inno Setup 5.1.5 are not recognised"],
    )

    def calculate_chunk(self, file: File, start_offset: int) -> ValidChunk | None:
        cert_end = certificate_end(file, start_offset)  # also proves a PE starts here
        end = max(start_offset + total_size(file, start_offset), cert_end)
        if end > len(file):
            raise InvalidInputFormat("Inno setup data runs past the end of the data")
        return ValidChunk(start_offset=start_offset, end_offset=end)
