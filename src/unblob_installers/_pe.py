"""PE/COFF layout shared by the PE-based installer handlers (FSD §17).

Only what chunking needs: that a PE starts here, and where its Authenticode
certificate table ends (the security data directory holds a file offset).
"""

import struct

from unblob.file_utils import InvalidInputFormat

PE32, PE32_PLUS = 0x10B, 0x20B
SECURITY_DIRECTORY = 4


def _unpack(fmt: str, buf, offset: int) -> tuple:
    if offset < 0 or offset + struct.calcsize(fmt) > len(buf):
        raise InvalidInputFormat("PE structure runs past the end of the data")
    return struct.unpack_from(fmt, buf, offset)


def _pe_header(buf, start: int) -> int:
    """Offset of the PE signature of the PE starting at start."""
    if bytes(buf[start : start + 2]) != b"MZ":
        raise InvalidInputFormat("no MZ header")
    (e_lfanew,) = _unpack("<I", buf, start + 0x3C)
    pe = start + e_lfanew
    if bytes(buf[pe : pe + 4]) != b"PE\0\0":
        raise InvalidInputFormat("no PE signature")
    return pe


def certificate_table(buf, start: int) -> tuple[int, int]:
    """Offset (relative to start) and size of the Authenticode table; (0, 0) if unsigned."""
    pe = _pe_header(buf, start)
    (magic,) = _unpack("<H", buf, pe + 24)
    if magic not in (PE32, PE32_PLUS):
        raise InvalidInputFormat("unknown optional header")
    directories = pe + 24 + (96 if magic == PE32 else 112)
    offset, size = _unpack("<II", buf, directories + 8 * SECURITY_DIRECTORY)
    return (offset, size) if size else (0, 0)


def certificate_end(buf, start: int) -> int:
    """End offset of the Authenticode table, or start if unsigned (FR-PE-01)."""
    offset, size = certificate_table(buf, start)
    return start + offset + size if size else start


def _sections(buf, start: int) -> list[tuple[bytes, int, int]]:
    """(name, raw pointer, raw size) of each section, pointers file-relative to start."""
    pe = _pe_header(buf, start)
    count, optional_size = _unpack("<H12xH", buf, pe + 6)
    table = pe + 24 + optional_size
    sections = []
    for i in range(count):
        name, raw_size, raw_pointer = _unpack("<8s8xII", buf, table + 40 * i)
        sections.append((name.rstrip(b"\0"), raw_pointer, raw_size))
    return sections


def overlay_start(buf, start: int) -> int:
    """Offset of the first byte after the last section's raw data."""
    ends = [pointer + size for _, pointer, size in _sections(buf, start) if size]
    return start + max(ends, default=0)


def find_section(buf, start: int, name: bytes) -> tuple[int, int] | None:
    """Absolute offset and raw size of the named section, if the PE has one."""
    for section, pointer, size in _sections(buf, start):
        if section == name:
            return start + pointer, size
    return None
