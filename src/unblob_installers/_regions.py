"""Sparse images as contiguous regions (FSD §17, OD-1).

A region is a run of consecutive addresses that the image writes. Gaps are
never filled, so the bytes written never exceed the bytes the image carries
(NFR-SEC-02).
"""

import bisect
import re
from collections.abc import Iterable
from pathlib import PurePosixPath

_UNSAFE = re.compile(rb"[^A-Za-z0-9._-]")


class OverlapConflictError(ValueError):
    """Two writes put different bytes at the same address."""

    def __init__(self, address: int, first: int, second: int):
        super().__init__(
            f"conflicting writes at 0x{address:08x} (sources {first} and {second})"
        )
        self.address = address
        self.first = first
        self.second = second


def assemble(writes: Iterable[tuple[int, bytes, int]]) -> list[tuple[int, bytes]]:
    """Merge (address, data, source id) writes into sorted contiguous regions.

    Identical overlapping writes are accepted; differing ones raise
    OverlapConflictError at the first differing byte, naming the write that
    put it there and the one that differs.
    """
    # Each region keeps its sources as spans (offset in the region where a
    # source's bytes begin, source), not one entry per byte (NFR-SEC-10).
    regions: list[tuple[int, bytearray, list[int], list[int]]] = []
    for address, data, source in sorted(writes, key=lambda w: (w[0], w[2])):
        if regions:
            start, buf, offsets, sources = regions[-1]
            end = start + len(buf)
            if address <= end:
                # The write may end inside the region: compare what both cover.
                at = address - start
                covered = buf[at : at + len(data)]
                if covered != data[: len(covered)]:
                    # Name the write that put the first differing byte there.
                    k = next(i for i, b in enumerate(covered) if b != data[i])
                    owner = sources[bisect.bisect_right(offsets, at + k) - 1]
                    raise OverlapConflictError(address + k, owner, source)
                if address + len(data) > end:
                    offsets.append(len(buf))
                    sources.append(source)
                    buf += data[end - address :]
                continue
        regions.append((address, bytearray(data), [0], [source]))
    return [(start, bytes(buf)) for start, buf, _, _ in regions]


def region_name(address: int) -> PurePosixPath:
    """Region file name: the start address as 8 lowercase hex digits."""
    return PurePosixPath(f"0x{address:08x}.bin")


def safe_name(raw: bytes, default: str) -> str:
    """Make a path component from input bytes (NFR-SEC-01).

    Trailing NUL padding is dropped, every byte outside [A-Za-z0-9._-] becomes
    "_", and an empty result, "." or ".." becomes default.
    """
    name = _UNSAFE.sub(b"_", raw.rstrip(b"\0")).decode("ascii")
    return default if name in ("", ".", "..") else name
