"""Region assembly shared by UF2, Intel HEX, .cyacd/.cyacd2 and GBL (FSD §18)."""

import tracemalloc

import pytest

from unblob_installers._regions import OverlapConflictError, assemble

KIB = 1024
MIB = 1024 * KIB


def contiguous(total: int, size: int, copies: int = 1) -> list[tuple[int, bytes, int]]:
    """Total bytes as size-byte writes at contiguous addresses, each `copies` times."""
    return [
        (n * size, bytes([n % 251]) * size, n * copies + c)
        for n in range(total // size)
        for c in range(copies)
    ]


def reference(writes: list[tuple[int, bytes, int]]) -> list[tuple[int, bytes]]:
    """Regions of non-conflicting writes, merged by a plain independent method."""
    by_address = {address: piece for address, piece, _ in writes}
    regions: list[tuple[int, bytearray]] = []
    for address in sorted(by_address):
        piece = by_address[address]
        if regions and regions[-1][0] + len(regions[-1][1]) == address:
            regions[-1][1].extend(piece)
        else:
            regions.append((address, bytearray(piece)))
    return [(start, bytes(buf)) for start, buf in regions]


CASES = {
    "16 MiB as 4 KiB writes": lambda: contiguous(16 * MIB, 4 * KIB),
    "the same, every write twice": lambda: contiguous(16 * MIB, 4 * KIB, copies=2),
    "16 MiB as 16-byte writes": lambda: contiguous(16 * MIB, 16),
    "4 MiB as 1-byte writes": lambda: contiguous(4 * MIB, 1),
    "1 MiB as 1-byte separate regions": lambda: [
        (2 * n, bytes([n % 251]), n) for n in range(MIB)
    ],
}


@pytest.mark.parametrize("case", CASES)
def test_tc_sec_10_assembly_memory_bounded(case: str):
    data = CASES[case]()  # built before measuring: the writes are not counted
    tracemalloc.start()
    try:
        regions = assemble(data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert regions == reference(data)  # each region equals the data written
    output = sum(len(buf) for _, buf in regions)
    bound = 3 * output + 128 * len(data) + 512 * len(regions) + MIB
    assert peak <= bound, f"{peak} bytes allocated, bound {bound}"


def test_tc_sec_10_conflict_names_the_two_writes_that_differ():
    a = (0, b"\x11" * 8, 1)
    b = (4, b"\x11" * 4 + b"\x22" * 4, 2)  # writes bytes 4-11; 8-11 are \x22
    c = (6, b"\x11" * 2 + b"\x22" * 3 + b"\x33", 3)  # differs from B at byte 11
    with pytest.raises(OverlapConflictError) as raised:
        assemble([a, b, c])
    assert (raised.value.first, raised.value.second) == (2, 3)  # B and C, not A
    assert raised.value.address == 11
