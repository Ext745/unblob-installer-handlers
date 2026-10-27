"""WiX/Burn bundle handler (FSD §9).

The engine's .wixburn section holds the Burn section header (WiX burn/engine
section.cpp): magic, version, bundle GUID, stub size, the original checksum
and signature, container format and the container sizes. The UX container
starts at the end of the stub; attached containers start at the end of the
engine, which section.cpp takes as the end of the original signature if one
is recorded, else of the PE's own signature, else of the UX container. The handler writes each container as a file; unblob's
CAB handler unpacks them on recursion.
"""

import struct
from pathlib import Path

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

from ._pe import certificate_end, certificate_table, find_section

SECTION_NAME = b".wixburn"
MAGIC = 0x00F14300
VERSION = 2
FORMAT_CAB = 1
HEADER = struct.Struct("<II16sIIIIII")  # magic … container count; sizes follow


def containers(
    header: bytes, signature: tuple[int, int] = (0, 0)
) -> list[tuple[str, int, int]]:
    """(file name, offset, size) per container; offsets relative to the bundle.

    signature is the PE's own Authenticode table (offset, size), (0, 0) if none.
    """
    if len(header) < HEADER.size:
        raise InvalidInputFormat(".wixburn section too short")
    magic, version, _guid, stub, _checksum, sig_offset, sig_size, fmt, count = (
        HEADER.unpack_from(header)
    )
    if magic != MAGIC or version != VERSION:
        raise InvalidInputFormat("no Burn section header")
    if fmt != FORMAT_CAB:
        raise InvalidInputFormat(f"Burn container format {fmt} is not CAB")
    if count == 0 or HEADER.size + 4 * count > len(header):
        raise InvalidInputFormat("Burn container count does not fit the section")
    ux_size, *attached = struct.unpack_from(f"<{count}I", header, HEADER.size)

    found = [("u0.cab", stub, ux_size)]
    if sig_offset:
        offset = sig_offset + sig_size
    elif signature[0]:
        offset = signature[0] + signature[1]
    else:
        offset = stub + ux_size
    for index, size in enumerate(attached):
        found.append((f"a{index}.cab", offset, size))
        offset += size
    return found


def _bundle_containers(file: File, start: int) -> list[tuple[str, int, int]]:
    section = find_section(file, start, SECTION_NAME)
    if section is None:
        raise InvalidInputFormat("no .wixburn section")
    offset, size = section
    return containers(
        bytes(file[offset : offset + size]), certificate_table(file, start)
    )


class WixBurnExtractor(Extractor):
    def extract(self, inpath: Path, outdir: Path) -> ExtractResult | None:
        fs = FileSystem(outdir)
        with File.from_path(inpath) as file:
            for name, offset, size in _bundle_containers(file, 0):
                fs.carve(Path(name), file, offset, size)
        return ExtractResult(reports=fs.problems)


class WixBurnHandler(Handler):
    NAME = "wix_burn"
    PATTERNS = [HexString("4D 5A")]  # every PE; the .wixburn section decides
    EXTRACTOR = WixBurnExtractor()
    DOC = HandlerDoc(
        name="WiX Burn bundle",
        description="WiX Burn bootstrapper bundle: a PE whose .wixburn section locates the UX container and the attached CAB containers appended to it, each written out as a file.",
        handler_type=HandlerType.EXECUTABLE,
        vendor="WiX Toolset",
        references=[
            Reference(title="WiX Toolset", url="https://wixtoolset.org/"),
            Reference(
                title="Burn section header (wix3 src/burn/engine/section.cpp)",
                url="https://github.com/wixtoolset/wix3/blob/develop/src/burn/engine/section.cpp",
            ),
        ],
        limitations=[
            "More than one attached container is verified on a hand-built header only",
        ],
    )

    def calculate_chunk(self, file: File, start_offset: int) -> ValidChunk | None:
        cert_end = certificate_end(file, start_offset)  # also proves a PE starts here
        containers_end = max(
            start_offset + offset + size
            for _, offset, size in _bundle_containers(file, start_offset)
        )
        end = max(containers_end, cert_end)
        if end > len(file):
            raise InvalidInputFormat("Burn container runs past the end of the data")
        return ValidChunk(start_offset=start_offset, end_offset=end)
