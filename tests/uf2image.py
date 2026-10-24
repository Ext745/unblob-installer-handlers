"""Independent UF2 reader for tests: the bytes a UF2 writes, by address.

Deliberately separate from unblob_installers.uf2 so the handler is never
checked against itself.
"""

import struct
from pathlib import Path


def payload_image(path: Path) -> tuple[int, bytes]:
    """(start address, contiguous bytes) written by a single-region UF2."""
    data = path.read_bytes()
    writes = []
    for off in range(0, len(data), 512):
        _m0, _m1, _flags, addr, size = struct.unpack_from("<5I", data, off)
        writes.append((addr, data[off + 32 : off + 32 + size]))
    writes.sort()
    start = writes[0][0]
    image = bytearray()
    for addr, chunk in writes:
        assert addr == start + len(image), "fixture is not one contiguous region"
        image += chunk
    return start, bytes(image)
