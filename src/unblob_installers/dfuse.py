"""DfuSe handler (FSD §12).

Format: ST UM0391 "DfuSe File Format Specification"; suffix and CRC per the
USB DFU 1.1 specification. A prefix, targets each holding elements, a suffix.
"""

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from unblob.file_utils import InvalidInputFormat
from unblob.models import (
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

from ._extract import require_whole_chunk
from ._regions import region_name, safe_name

PREFIX = struct.Struct("<5sBIB")  # signature, version, image size, targets
TARGET = struct.Struct("<6sBI255sII")  # signature, alt, named, name, size, elements
ELEMENT = struct.Struct("<II")  # address, size
SUFFIX_SIZE = 16


@dataclass(frozen=True)
class Element:
    alt: int
    name: bytes | None
    address: int
    offset: int  # of the element's data, relative to the chunk start
    size: int


def element_path(alt: int, name: bytes | None, address: int) -> PurePosixPath:
    """`target<alt>_<name>/0x<address>.bin` (FR-DFU-05)."""
    target = safe_name(name, "unnamed") if name is not None else "unnamed"
    return PurePosixPath(f"target{alt}_{target}") / region_name(address)


def _read(buf, offset: int, layout: struct.Struct) -> tuple:
    if offset + layout.size > len(buf):
        raise InvalidInputFormat("DfuSe structure runs past the end of the data")
    return layout.unpack_from(buf, offset)


def _target_elements(buf, start: int, pos: int) -> tuple[int, list[Element]]:
    signature, alt, named, name, size, count = _read(buf, pos, TARGET)
    if signature != b"Target":
        raise InvalidInputFormat("missing Target prefix")
    pos += TARGET.size
    end = pos + size
    if end > len(buf):
        raise InvalidInputFormat("target runs past the end of the data")
    elements = []
    for _ in range(count):
        address, esize = _read(buf, pos, ELEMENT)
        pos += ELEMENT.size
        elements.append(
            Element(alt, name if named else None, address, pos - start, esize)
        )
        pos += esize
    if pos != end:
        raise InvalidInputFormat("element sizes do not sum to the target size")
    return end, elements


def parse(buf, start: int) -> tuple[int, list[Element]]:
    """(chunk end, elements) of the DfuSe file at start; InvalidInputFormat if invalid."""
    signature, version, image_size, targets = _read(buf, start, PREFIX)
    if signature != b"DfuSe" or version != 1 or targets == 0:
        raise InvalidInputFormat("not a DfuSe prefix")
    pos = start + PREFIX.size
    elements: list[Element] = []
    for _ in range(targets):
        pos, found = _target_elements(buf, start, pos)
        elements += found
    end = pos + SUFFIX_SIZE
    if end > len(buf) or bytes(buf[pos + 8 : pos + 12]) != b"UFD\x10":
        raise InvalidInputFormat("no DFU suffix after the last target")
    # Producers disagree on whether the image size counts the suffix (FSD 0.9.0).
    if image_size not in (pos - start, end - start):
        raise InvalidInputFormat("image size matches neither convention")
    (crc,) = struct.unpack_from("<I", buf, end - 4)
    if crc != zlib.crc32(buf[start : end - 4]) ^ 0xFFFFFFFF:
        raise InvalidInputFormat("DFU suffix CRC mismatch")
    return end, elements


class DfuSeExtractor(Extractor):
    def extract(self, inpath: Path, outdir: Path) -> ExtractResult | None:
        require_whole_chunk(DfuSeHandler().calculate_chunk, inpath)
        data = inpath.read_bytes()
        _end, elements = parse(data, 0)
        for element in elements:
            target = outdir / element_path(element.alt, element.name, element.address)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data[element.offset : element.offset + element.size])
        return ExtractResult(reports=[])


class DfuSeHandler(Handler):
    NAME = "dfuse"
    PATTERNS = [HexString("44 66 75 53 65 01")]  # "DfuSe", version 1
    EXTRACTOR = DfuSeExtractor()
    DOC = HandlerDoc(
        name="DfuSe",
        description="ST DfuSe firmware file (.dfu): targets holding address-tagged elements, with a DFU 1.1 suffix and CRC; used by STM32 and GD32 update tools.",
        handler_type=HandlerType.ARCHIVE,
        vendor="STMicroelectronics",
        references=[
            Reference(
                title="UM0391 DfuSe File Format Specification",
                url="https://www.st.com/resource/en/user_manual/um0391-dfuse-file-format-specification-stmicroelectronics.pdf",
            ),
            Reference(
                title="USB Device Firmware Upgrade 1.1",
                url="https://www.usb.org/sites/default/files/DFU_1.1.pdf",
            ),
        ],
        limitations=["Suffix-only DFU files (no DfuSe prefix) are not handled"],
    )

    def calculate_chunk(self, file: File, start_offset: int) -> ValidChunk | None:
        end, _elements = parse(file, start_offset)
        return ValidChunk(start_offset=start_offset, end_offset=end)
