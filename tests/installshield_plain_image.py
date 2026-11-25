"""Build InstallShield plain-layout setup.exe files for tests (FSD §13a), from §13a.1 alone.

A minimal PE32 (one section, raw data at 0x200..0x400, so the PE image ends
at 0x400), followed by the package: ANSI plain = per file four
NUL-terminated strings (source name, destination name, version, decimal data
length), then the data; UTF-16 plain = a file count (u32 LE), then per file
the same four strings in UTF-16LE ending in a 2-byte NUL, then the data. An
optional certificate table follows after `gap` bytes, the security directory
pointing to it.

Usage: python3 tests/installshield_plain_image.py <payload> <outdir>
"""

import struct
import sys
from pathlib import Path

IMAGE_END = 0x400
SECURITY_DIRECTORY = 4


def minimal_pe() -> bytearray:
    pe = bytearray(IMAGE_END)
    pe[0:2] = b"MZ"
    struct.pack_into("<I", pe, 0x3C, 0x40)
    pe[0x40:0x44] = b"PE\0\0"
    # machine i386, 1 section, optional header 224 bytes, executable image
    struct.pack_into("<HHIIIHH", pe, 0x44, 0x14C, 1, 0, 0, 0, 224, 0x0102)
    optional = 0x58
    struct.pack_into("<H", pe, optional, 0x10B)  # PE32
    struct.pack_into("<I", pe, optional + 60, 0x200)  # SizeOfHeaders
    struct.pack_into("<I", pe, optional + 92, 16)  # NumberOfRvaAndSizes
    section = optional + 224
    pe[section : section + 8] = b".text\0\0\0"
    # virtual size, virtual address, raw size, raw pointer
    struct.pack_into("<IIII", pe, section + 8, 0x200, 0x1000, 0x200, 0x200)
    pe[0x200:0x400] = b"\xc3" * 0x200  # ret
    return pe


def pe_with_sections(count: int) -> bytes:
    """Build a PE32 declaring count sections, with their all-zero table.

    Nothing follows the headers: no section data and no overlay.
    """
    optional = 0x58
    table = optional + 224
    size_of_headers = -(-(table + 40 * count) // 0x200) * 0x200
    pe = bytearray(size_of_headers)
    pe[: 0x58 + 224] = minimal_pe()[: 0x58 + 224]
    struct.pack_into("<H", pe, 0x46, count)  # NumberOfSections
    struct.pack_into("<I", pe, optional + 60, size_of_headers)
    return bytes(pe)


def with_certificate(pe_and_package: bytes, gap: bytes, certificate: bytes) -> bytes:
    """Append gap + certificate and point the security directory at it."""
    data = bytearray(pe_and_package + gap)
    offset = len(data)
    directory = 0x58 + 96 + 8 * SECURITY_DIRECTORY
    struct.pack_into("<II", data, directory, offset, len(certificate))
    return bytes(data + certificate)


def ansi(files: list[tuple[str, str, str, bytes]]) -> bytes:
    out = []
    for source, destination, version, data in files:
        for field in (source, destination, version, str(len(data))):
            out.append(field.encode("latin-1") + b"\0")
        out.append(data)
    return b"".join(out)


def utf16(files: list[tuple[str, str, str, bytes]]) -> bytes:
    out = [struct.pack("<I", len(files))]
    for source, destination, version, data in files:
        for field in (source, destination, version, str(len(data))):
            out.append(field.encode("utf-16-le") + b"\0\0")
        out.append(data)
    return b"".join(out)


def files(payload: bytes) -> list[tuple[str, str, str, bytes]]:
    return [
        (
            "setup.exe",
            "Disk1\\setup.exe",
            "1.0.0.2",  # scrub:allow version number
            payload[:2000],
        ),
        ("data1.hdr", "Disk1\\data1.hdr", "0.0.0.0", payload[2000:3000]),  # noqa: S104 - a version string
        ("readme.txt", "Disk1\\readme é.txt", "0.0.0.0", b"read me\r\n"),  # noqa: S104 - a version string
    ]


def setup_exe(package: bytes) -> bytes:
    return bytes(minimal_pe()) + package


def main(payload_path: str, outdir: str) -> None:
    payload = Path(payload_path).read_bytes()
    out = Path(outdir)
    (out / "ansi.exe").write_bytes(setup_exe(ansi(files(payload))))
    (out / "utf16.exe").write_bytes(setup_exe(utf16(files(payload))))


if __name__ == "__main__":
    main(*sys.argv[1:])
