"""WiX/Burn pure core (FSD §9): the container walk over a .wixburn header."""

import importlib
import struct
from types import ModuleType


def wix_burn() -> ModuleType:
    # Imported per test, so the file is collected before the module exists.
    return importlib.import_module("unblob_installers.wix_burn")


def header(stub: int, sig: tuple[int, int], sizes: list[int]) -> bytes:
    return struct.pack(
        f"<II16s6I{len(sizes)}I",
        0x00F14300,
        2,
        bytes(16),
        stub,
        0,
        *sig,
        1,
        len(sizes),
        *sizes,
    )


def test_tc_burn_07_container_walk_three_attached():
    walk = wix_burn().containers
    assert walk(header(0x1000, (0, 0), [100, 10, 20, 30])) == [
        ("u0.cab", 0x1000, 100),
        ("a0.cab", 0x1064, 10),
        ("a1.cab", 0x106E, 20),
        ("a2.cab", 0x1082, 30),
    ]
    # Signed: attached containers start after the original signature.
    assert walk(header(0x1000, (0x1068, 0x40), [100, 10, 20, 30]))[1:] == [
        ("a0.cab", 0x10A8, 10),
        ("a1.cab", 0x10B2, 20),
        ("a2.cab", 0x10C6, 30),
    ]
