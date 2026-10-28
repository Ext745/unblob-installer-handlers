"""DfuSe pure core (FSD §12): validation and element file naming."""

import importlib
import struct
import zlib
from pathlib import Path
from types import ModuleType

import pytest
from unblob.file_utils import File, InvalidInputFormat

from tests.conftest import INPUTS


def dfuse() -> ModuleType:
    # Imported per test, so the file is collected before the module exists.
    return importlib.import_module("unblob_installers.dfuse")


def test_tc_dfu_05_element_path():
    path = dfuse().element_path
    assert str(path(0, b"Internal Flash\0\0\0", 0x08000000)) == (
        "target0_Internal_Flash/0x08000000.bin"
    )
    assert str(path(1, None, 0x1FFF7800)) == "target1_unnamed/0x1fff7800.bin"


FIXTURE = (INPUTS["dfuse"] / "standard.dfu").read_bytes()
PREFIX_SIZE, TARGET_SIZE = 11, 274  # UM0391: DfuSe prefix, Target prefix
ELEMENT_SIZE_FIELD = PREFIX_SIZE + TARGET_SIZE + 4  # first element's dwElementSize


def with_crc(data: bytes) -> bytes:
    """Recompute the DFU suffix CRC, so only the field under test is wrong."""
    crc = zlib.crc32(data[:-4]) ^ 0xFFFFFFFF
    return data[:-4] + struct.pack("<I", crc)


def claimed(data: bytes) -> bool:
    with File.from_bytes(data) as file:
        try:
            dfuse().DfuSeHandler().calculate_chunk(file, 0)
        except InvalidInputFormat:
            return False
    return True


def test_tc_dfu_02_flipped_crc_byte_is_not_claimed():
    assert claimed(FIXTURE)
    flipped = bytearray(FIXTURE)
    flipped[-1] ^= 0x01
    assert not claimed(bytes(flipped))


def test_tc_dfu_03_element_size_off_by_one_is_not_claimed():
    (size,) = struct.unpack_from("<I", FIXTURE, ELEMENT_SIZE_FIELD)
    grown = bytearray(FIXTURE)
    struct.pack_into("<I", grown, ELEMENT_SIZE_FIELD, size + 1)
    assert not claimed(with_crc(bytes(grown)))


def test_tc_dfu_03_image_size_of_neither_convention_is_not_claimed():
    (image_size,) = struct.unpack_from("<I", FIXTURE, 6)
    for wrong in (image_size + 1, image_size - 1):
        changed = bytearray(FIXTURE)
        struct.pack_into("<I", changed, 6, wrong)
        assert not claimed(with_crc(bytes(changed))), wrong


NAMED_FIELD = PREFIX_SIZE + 6 + 1  # "Target", bAlternateSetting, then bTargetNamed
NAME_FIELD = NAMED_FIELD + 4  # szTargetName, 255 bytes


def named_target(name: bytes) -> bytes:
    data = bytearray(FIXTURE)
    struct.pack_into("<I", data, NAMED_FIELD, 1)
    data[NAME_FIELD : NAME_FIELD + 255] = name.ljust(255, b"\0")
    return with_crc(bytes(data))


@pytest.mark.parametrize(
    "name,directory",
    [
        (b"../../x/../etc", "target0_.._.._x_.._etc"),
        (b"a\0b/c\\d\xff", "target0_a_b_c_d_"),
        (b"..", "target0_unnamed"),
    ],
    ids=["traversal", "nul-slash-backslash", "dotdot"],
)
def test_tc_sec_01_target_name_stays_beneath_the_output(
    tmp_path: Path, name: bytes, directory: str
):
    source = tmp_path / "in.dfu"
    source.write_bytes(named_target(name))
    out = tmp_path / "x" / "out"
    out.mkdir(parents=True)
    dfuse().DfuSeExtractor().extract(source, out)

    written = [p for p in (tmp_path / "x").rglob("*") if p.is_file()]
    assert [str(p.relative_to(out)) for p in written] == [f"{directory}/0x08000000.bin"]
    assert all(p.resolve().is_relative_to(out.resolve()) for p in written)
    assert not (tmp_path / "etc").exists()
    assert not (tmp_path / "x" / "etc").exists()


def dfuse_file(
    targets: list[tuple[int, bytes | None, list[tuple[int, bytes]]]],
) -> bytes:
    """Build a DfuSe file (UM0391) with the given (alt, name, elements) targets."""
    body = b""
    for alt, name, elements in targets:
        data = b"".join(struct.pack("<II", a, len(d)) + d for a, d in elements)
        named = 1 if name is not None else 0
        body += (
            b"Target"
            + struct.pack("<BI", alt, named)
            + (name or b"").ljust(255, b"\0")
            + struct.pack("<II", len(data), len(elements))
            + data
        )
    suffix = struct.pack("<HHHH", 0xFFFF, 0xDF11, 0x0483, 0x011A) + b"UFD" + bytes([16])
    size = PREFIX_SIZE + len(body) + len(suffix) + 4  # dfuse-pack: suffix included
    prefix = b"DfuSe\x01" + struct.pack("<IB", size, len(targets))
    return with_crc(prefix + body + suffix + bytes(4))


def test_tc_dfu_08_one_file_per_element_never_merged(tmp_path: Path):
    # Two targets, three elements; target 0's two elements are contiguous, so
    # merging contiguous ranges would make them one file.
    data = dfuse_file(
        [
            (
                0,
                b"Internal Flash",
                [(0x08000000, b"\x11" * 16), (0x08000010, b"\x22" * 16)],
            ),
            (1, None, [(0x1FFF7800, b"\x33" * 8)]),
        ]
    )
    assert claimed(data)
    source = tmp_path / "in.dfu"
    source.write_bytes(data)
    out = tmp_path / "out"
    out.mkdir()
    dfuse().DfuSeExtractor().extract(source, out)
    files = {
        str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()
    }
    assert files == {
        "target0_Internal_Flash/0x08000000.bin": b"\x11" * 16,
        "target0_Internal_Flash/0x08000010.bin": b"\x22" * 16,
        "target1_unnamed/0x1fff7800.bin": b"\x33" * 8,
    }
