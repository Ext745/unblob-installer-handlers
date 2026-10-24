"""UF2 pure core (FSD §10): block recognition and region naming."""

import importlib
import struct
from types import ModuleType

import pytest

MAGIC_START0, MAGIC_START1, MAGIC_END = 0x0A324655, 0x9E5D5157, 0x0AB16F30
FLAG_FAMILY = 0x00002000
RP2040 = 0xE48BFF56


def uf2() -> ModuleType:
    # Imported per test, so the file is collected before the module exists.
    return importlib.import_module("unblob_installers.uf2")


def block(addr: int, data: bytes, n: int = 0, total: int = 1) -> bytes:
    head = struct.pack(
        "<8I",
        MAGIC_START0,
        MAGIC_START1,
        FLAG_FAMILY,
        addr,
        len(data),
        n,
        total,
        RP2040,
    )
    return head + data.ljust(476, b"\0") + struct.pack("<I", MAGIC_END)


@pytest.mark.xfail(reason="FR-UF2-01: uf2 handler absent", strict=True)
def test_tc_uf2_01_block_recognised_by_three_magics():
    b = uf2().parse_block(block(0x10000000, b"\xaa" * 256))
    assert b is not None
    assert (b.target_addr, b.payload, b.family_id) == (
        0x10000000,
        b"\xaa" * 256,
        RP2040,
    )


@pytest.mark.xfail(reason="FR-UF2-05: uf2 handler absent", strict=True)
def test_tc_uf2_05_region_file_name():
    assert str(uf2().region_path(RP2040, 0x10000000)) == "RP2040/0x10000000.bin"
    assert str(uf2().region_path(RP2040, 0x0000ABCD)) == "RP2040/0x0000abcd.bin"
