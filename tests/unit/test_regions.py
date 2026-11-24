"""Region assembly shared by UF2, Intel HEX, .cyacd/.cyacd2 and GBL (FSD §18)."""

import tracemalloc

import pytest

from unblob_installers._regions import OverlapConflictError, assemble

KIB = 1024
MIB = 1024 * KIB
TOTAL = 16 * MIB
PIECE = 4 * KIB


def writes(copies: int) -> list[tuple[int, bytes, int]]:
    """16 MiB as 4 KiB writes at contiguous addresses, each given `copies` times."""
    pieces = [bytes([n % 251]) * PIECE for n in range(TOTAL // PIECE)]
    return [
        (n * PIECE, piece, n * copies + c)
        for n, piece in enumerate(pieces)
        for c in range(copies)
    ]


@pytest.mark.parametrize("copies", [1, 2], ids=["contiguous", "every write twice"])
def test_tc_sec_10_assembly_memory_bounded(copies: int):
    data = writes(copies)  # built before measuring: the writes are not counted
    expected = b"".join(piece for _, piece, s in data if s % copies == 0)
    tracemalloc.start()
    try:
        regions = assemble(data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert regions == [(0, expected)]
    assert peak <= 3 * TOTAL + MIB, f"{peak} bytes allocated for {TOTAL} bytes"


def test_tc_sec_10_conflict_still_names_both_sources():
    first = b"\x11" * PIECE
    second = b"\x11" * (PIECE - 1) + b"\x22"  # differs in its last byte
    with pytest.raises(OverlapConflictError) as raised:
        assemble([(0x1000, first, 7), (0x1000, second, 9)])
    assert (raised.value.first, raised.value.second) == (7, 9)
