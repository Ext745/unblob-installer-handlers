"""Sparse images as contiguous regions (FSD §17, OD-1).

A region is a run of consecutive addresses that the image writes. Gaps are
never filled, so the bytes written never exceed the bytes the image carries
(NFR-SEC-02).
"""

from collections.abc import Iterable
from pathlib import PurePosixPath


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
    OverlapConflictError naming both sources.
    """
    regions: list[tuple[int, bytearray, list[int]]] = []
    for address, data, source in sorted(writes, key=lambda w: (w[0], w[2])):
        if regions:
            start, buf, sources = regions[-1]
            end = start + len(buf)
            if address <= end:
                overlap = buf[address - start : end]
                if bytes(overlap) != data[: len(overlap)]:
                    raise OverlapConflictError(
                        address, sources[address - start], source
                    )
                tail = data[len(overlap) :]
                buf += tail
                sources += [source] * len(tail)
                continue
        regions.append((address, bytearray(data), [source] * len(data)))
    return [(start, bytes(buf)) for start, buf, _ in regions]


def region_name(address: int) -> PurePosixPath:
    """Region file name: the start address as 8 lowercase hex digits."""
    return PurePosixPath(f"0x{address:08x}.bin")
