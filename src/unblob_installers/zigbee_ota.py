"""Zigbee OTA upgrade file handler (FSD §13c).

Format: Zigbee Cluster Library, OTA Upgrade cluster, "OTA Upgrade File
Format"; header table as Digi publishes it. All fields little-endian.
"""

import struct
from dataclasses import dataclass
from pathlib import Path

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
from unblob.report import Report

from ._extract import require_whole_chunk

FILE_ID = 0x0BEEF11E
HEADER_VERSION = 0x0100
# file id, header version, header length, field control, manufacturer code,
# image type, file version, stack version, header string, total image size
HEADER = struct.Struct("<IHHHHHIH32sI")  # 56 bytes
SUB_HEADER = struct.Struct("<HI")  # tag id, length


class ZigbeeOtaReport(Report):
    """Zigbee OTA header fields (FR-ZOTA-05)."""

    manufacturer_code: int
    image_type: int
    file_version: int
    stack_version: int
    header_string: str


@dataclass(frozen=True)
class OtaInfo:
    header_length: int
    total_size: int
    manufacturer_code: int
    image_type: int
    file_version: int
    stack_version: int
    header_string: str
    subelements: list[tuple[int, int, int]]  # tag, data offset, length (relative)


def _optional_size(field_control: int) -> int:
    """Bytes of the optional header fields field control selects."""
    return (
        (1 if field_control & 0x1 else 0)  # security credential version
        + (8 if field_control & 0x2 else 0)  # upgrade file destination
        + (4 if field_control & 0x4 else 0)  # minimum, maximum hardware version
    )


def ota_info(file: File, start: int, size: int) -> OtaInfo:
    """Parse the OTA file at start in an input of size bytes; InvalidInputFormat if not one."""
    if start + HEADER.size > size:
        raise InvalidInputFormat("OTA header runs past the end of the input")
    file.seek(start)
    (
        file_id,
        header_version,
        header_length,
        field_control,
        manufacturer,
        image_type,
        file_version,
        stack_version,
        header_string,
        total,
    ) = HEADER.unpack(file.read(HEADER.size))
    if file_id != FILE_ID or header_version != HEADER_VERSION:
        raise InvalidInputFormat("not a Zigbee OTA header")
    if header_length != HEADER.size + _optional_size(field_control):
        raise InvalidInputFormat("header length does not match field control")
    if total <= header_length or start + total > size:
        raise InvalidInputFormat("total image size out of range")
    subelements = []
    pos = header_length
    while pos < total:
        if pos + SUB_HEADER.size > total:
            raise InvalidInputFormat("sub-element header cut by the image end")
        file.seek(start + pos)
        tag, length = SUB_HEADER.unpack(file.read(SUB_HEADER.size))
        data = pos + SUB_HEADER.size
        if data + length > total:
            raise InvalidInputFormat("sub-element runs past the image end")
        subelements.append((tag, data, length))
        pos = data + length
    return OtaInfo(
        header_length=header_length,
        total_size=total,
        manufacturer_code=manufacturer,
        image_type=image_type,
        file_version=file_version,
        stack_version=stack_version,
        header_string=header_string.rstrip(b"\0").decode("latin-1"),
        subelements=subelements,
    )


class ZigbeeOtaExtractor(Extractor):
    def extract(self, inpath: Path, outdir: Path) -> ExtractResult | None:
        require_whole_chunk(ZigbeeOtaHandler().calculate_chunk, inpath)
        with File.from_path(inpath) as file:
            info = ota_info(file, 0, inpath.stat().st_size)
            for index, (tag, offset, length) in enumerate(info.subelements):
                file.seek(offset)
                (outdir / f"tag_0x{tag:04x}_{index}.bin").write_bytes(file.read(length))
        return ExtractResult(
            reports=[
                ZigbeeOtaReport(
                    manufacturer_code=info.manufacturer_code,
                    image_type=info.image_type,
                    file_version=info.file_version,
                    stack_version=info.stack_version,
                    header_string=info.header_string,
                )
            ]
        )


class ZigbeeOtaHandler(Handler):
    NAME = "zigbee_ota"
    PATTERNS = [
        HexString("1E F1 EE 0B 00 01")
    ]  # file identifier, header version 0x0100
    EXTRACTOR = ZigbeeOtaExtractor()
    DOC = HandlerDoc(
        name="Zigbee OTA upgrade file",
        description="Over-the-air upgrade file of the Zigbee Cluster Library OTA Upgrade cluster: a header and tagged sub-elements, the upgrade image (often a vendor image such as a Silicon Labs GBL) among them.",
        handler_type=HandlerType.ARCHIVE,
        vendor="Connectivity Standards Alliance (Zigbee)",
        references=[
            Reference(
                title="Zigbee Cluster Library Specification, OTA Upgrade cluster",
                url="https://csa-iot.org/developer-resource/specifications-download-request/",
            ),
            Reference(
                title="Digi: OTA files (header layout)",
                url="https://docs.digi.com/resources/documentation/digidocs/90001539/reference/r_ota_files.htm",
            ),
        ],
        limitations=[
            "Signatures and certificates in sub-elements are written as stored, not verified",
        ],
    )

    def calculate_chunk(self, file: File, start_offset: int) -> ValidChunk | None:
        file.seek(0, 2)
        size = file.tell()
        info = ota_info(file, start_offset, size)
        return ValidChunk(
            start_offset=start_offset, end_offset=start_offset + info.total_size
        )
