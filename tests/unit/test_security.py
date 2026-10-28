"""Resource bounds (FSD NFR-SEC-02, -03): output and reads stay within the input."""

import struct
import tracemalloc
from pathlib import Path

import pytest
from unblob.file_utils import File, InvalidInputFormat

from tests.conftest import FIXTURES
from tests.samples import handler

UF2_MAGICS = (0x0A324655, 0x9E5D5157, 0x0AB16F30)


def uf2_block(address: int, n: int, total: int) -> bytes:
    head = struct.pack("<8I", *UF2_MAGICS[:2], 0, address, 256, n, total, 0)
    return head + bytes([n + 1]) * 256 + bytes(220) + struct.pack("<I", UF2_MAGICS[2])


def hex_record(rtype: int, address: int, data: bytes) -> bytes:
    body = bytes([len(data), address >> 8, address & 0xFF, rtype]) + data
    return b":" + (body + bytes([-sum(body) & 0xFF])).hex().upper().encode() + b"\n"


def hex_at(*addresses: int) -> bytes:
    text = b""
    for address in addresses:
        text += hex_record(0x04, 0, struct.pack(">H", address >> 16))
        text += hex_record(0x00, address & 0xFFFF, b"\x5a" * 16)
    return text + hex_record(0x01, 0, b"")


CASES = {
    # The contract's cases: ~4 GiB between two writes.
    "uf2-4gib": ("uf2", uf2_block(0x00000000, 0, 2) + uf2_block(0xFFFFFE00, 1, 2)),
    "ihex-4gib": ("ihex", hex_at(0x00000000, 0xFFFF0000)),
    # A small gap, so a filler that pads only short gaps is still caught.
    "uf2-32kib": ("uf2", uf2_block(0x1000, 0, 2) + uf2_block(0x9000, 1, 2)),
    "ihex-32kib": ("ihex", hex_at(0x08001000, 0x08009000)),
    "dfuse": ("dfuse", (FIXTURES / "dfuse" / "standard.dfu").read_bytes()),
    "mcuboot": ("mcuboot", (FIXTURES / "mcuboot" / "standard.bin").read_bytes()),
}


@pytest.mark.parametrize("case", CASES)
def test_tc_sec_02_output_never_exceeds_the_chunk(case: str, tmp_path: Path):
    name, data = CASES[case]
    source = tmp_path / "in.bin"
    source.write_bytes(data)
    out = tmp_path / "out"
    out.mkdir()
    extractor = handler(name).EXTRACTOR
    assert extractor is not None
    extractor.extract(source, out)

    written = [p for p in out.rglob("*") if p.is_file()]
    assert written
    assert sum(p.stat().st_size for p in written) <= len(data)


MAX = 0xFFFFFFFF
KIB = 1024


def dfuse_header(
    image: int = 0x200, target: int = 0x88, element: int = 0x80, count: int = 1
) -> bytes:
    prefix = b"DfuSe\x01" + struct.pack("<IB", image, 1)
    target_prefix = b"Target" + struct.pack("<BI255sII", 0, 0, b"", target, count)
    return prefix + target_prefix + struct.pack("<II", 0x08000000, element)


def mcuboot_header(hdr: int = 0x20, protected: int = 0, image: int = 0x100) -> bytes:
    # magic, load address, sizes, flags, version major.minor.revision+build, pad
    return struct.pack(
        "<IIHHIIBBHII", 0x96F3B83D, 0, hdr, protected, image, 0, 1, 2, 3, 4, 0
    )


BIG_HEADERS = {
    "uf2-payload-size": (
        "uf2",
        struct.pack("<8I", *UF2_MAGICS[:2], 0, 0, MAX, 0, 1, 0)
        + bytes(476)
        + struct.pack("<I", UF2_MAGICS[2]),
    ),
    "ihex-byte-count": ("ihex", b":FF0000000102030405\n"),
    "dfuse-image-size": ("dfuse", dfuse_header(image=MAX)),
    "dfuse-target-size": ("dfuse", dfuse_header(target=MAX)),
    "dfuse-element-size": ("dfuse", dfuse_header(element=MAX)),
    # Zero-sized elements walk off the 1 KiB before the count runs out.
    "dfuse-element-count": ("dfuse", dfuse_header(element=0, count=MAX)),
    "mcuboot-image-size": ("mcuboot", mcuboot_header(image=MAX)),
    "mcuboot-header-size": ("mcuboot", mcuboot_header(hdr=0xFFFF)),
    "mcuboot-protected-size": ("mcuboot", mcuboot_header(protected=0xFFFF)),
    "mcuboot-tlv-total": (
        "mcuboot",
        mcuboot_header(image=0) + struct.pack("<HH", 0x6907, 0xFFFF),
    ),
}


@pytest.mark.parametrize("case", BIG_HEADERS)
def test_tc_sec_03_huge_declared_size_declined_within_the_file(case: str):
    name, header = BIG_HEADERS[case]
    data = header.ljust(KIB, b"\0")
    tracemalloc.start()
    try:
        with File.from_bytes(data) as file, pytest.raises(InvalidInputFormat):
            handler(name).calculate_chunk(file, 0)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 1024 * KIB, f"{peak} bytes allocated for a {KIB}-byte input"
