"""UF2 pure core (FSD §10): block recognition and region naming."""

import importlib
import struct
from pathlib import Path
from types import ModuleType

MAGIC_START0, MAGIC_START1, MAGIC_END = 0x0A324655, 0x9E5D5157, 0x0AB16F30
FLAG_FAMILY = 0x00002000
FLAG_NOT_MAIN = 0x00000001
RP2040 = 0xE48BFF56


def uf2() -> ModuleType:
    # Imported per test, so the file is collected before the module exists.
    return importlib.import_module("unblob_installers.uf2")


def block(
    addr: int,
    data: bytes,
    n: int = 0,
    total: int = 1,
    flags: int = FLAG_FAMILY,
    family: int = RP2040,
) -> bytes:
    head = struct.pack(
        "<8I",
        MAGIC_START0,
        MAGIC_START1,
        flags,
        addr,
        len(data),
        n,
        total,
        family if flags & FLAG_FAMILY else 0,
    )
    return head + data.ljust(476, b"\0") + struct.pack("<I", MAGIC_END)


def test_tc_uf2_01_block_recognised_by_three_magics():
    b = uf2().parse_block(block(0x10000000, b"\xaa" * 256))
    assert b is not None
    assert (b.target_addr, b.payload, b.family_id) == (
        0x10000000,
        b"\xaa" * 256,
        RP2040,
    )


def test_tc_uf2_05_region_file_name():
    assert str(uf2().region_path(RP2040, 0x10000000)) == "RP2040/0x10000000.bin"
    assert str(uf2().region_path(RP2040, 0x0000ABCD)) == "RP2040/0x0000abcd.bin"


def extract(tmp_path: Path, *blocks: bytes) -> dict[str, bytes]:
    """Run the UF2 extractor on the blocks; every output file and its bytes."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "in.uf2"
    source.write_bytes(b"".join(blocks))
    out = tmp_path / "out"
    out.mkdir()
    uf2().UF2Extractor().extract(source, out)
    return {
        str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()
    }


def test_tc_uf2_06_family_directory_for_missing_and_unknown_ids(tmp_path: Path):
    assert extract(tmp_path / "none", block(0x2000, b"\x11" * 256, flags=0)) == {
        "no_family/0x00002000.bin": b"\x11" * 256
    }
    unknown = block(0x2000, b"\x22" * 256, family=0x12345678)
    assert extract(tmp_path / "unknown", unknown) == {
        "0x12345678/0x00002000.bin": b"\x22" * 256
    }


def test_tc_uf2_07_not_main_flash_block_contributes_nothing(tmp_path: Path):
    files = extract(
        tmp_path,
        block(0x1000, b"\xaa" * 256, 0, 3),
        block(0x1100, b"\xbb" * 256, 1, 3, flags=FLAG_FAMILY | FLAG_NOT_MAIN),
        block(0x1200, b"\xcc" * 256, 2, 3),
    )
    assert b"\xbb" not in b"".join(files.values())
    assert files == {
        "RP2040/0x00001000.bin": b"\xaa" * 256,
        "RP2040/0x00001200.bin": b"\xcc" * 256,
    }
