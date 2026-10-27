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


def certificate_end(buf, start: int) -> int:
    """End offset of the Authenticode table, or start if unsigned (FR-PE-01)."""
    if bytes(buf[start : start + 2]) != b"MZ":
        raise InvalidInputFormat("no MZ header")
    (e_lfanew,) = _unpack("<I", buf, start + 0x3C)
    pe = start + e_lfanew
    if bytes(buf[pe : pe + 4]) != b"PE\0\0":
        raise InvalidInputFormat("no PE signature")
    (magic,) = _unpack("<H", buf, pe + 24)
    if magic not in (PE32, PE32_PLUS):
        raise InvalidInputFormat("unknown optional header")
    directories = pe + 24 + (96 if magic == PE32 else 112)
    offset, size = _unpack("<II", buf, directories + 8 * SECURITY_DIRECTORY)
    return start + offset + size if size else start
