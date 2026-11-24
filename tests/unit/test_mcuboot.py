"""MCUboot pure core (FSD §13): TLV areas, signed and encrypted."""

import importlib
import struct
from pathlib import Path
from types import ModuleType

import pytest
from unblob.file_utils import InvalidInputFormat

from tests.conftest import INPUTS

FIXTURE = (INPUTS["mcuboot"] / "standard.bin").read_bytes()


def mcuboot() -> ModuleType:
    # Imported per test, so the file is collected before the module exists.
    return importlib.import_module("unblob_installers.mcuboot")


def with_tlv_area(image: bytes, tlvs: list[tuple[int, bytes]]) -> bytes:
    """Replace the fixture's TLV area with the given (type, value) TLVs."""
    hdr_size, prot_size, img_size = struct.unpack_from("<HHI", image, 8)
    body = image[: hdr_size + img_size + prot_size]
    entries = b"".join(struct.pack("<HH", t, len(v)) + v for t, v in tlvs)
    return body + struct.pack("<HH", 0x6907, 4 + len(entries)) + entries


def with_protected_area(image: bytes, tlvs: list[tuple[int, bytes]]) -> bytes:
    """Give an image without protected TLVs a protected area of the given TLVs."""
    hdr_size, prot_size, img_size = struct.unpack_from("<HHI", image, 8)
    assert prot_size == 0
    entries = b"".join(struct.pack("<HH", t, len(v)) + v for t, v in tlvs)
    area = struct.pack("<HH", 0x6908, 4 + len(entries)) + entries
    header = image[:10] + struct.pack("<H", len(area)) + image[12:hdr_size]
    end = hdr_size + img_size
    return header + image[hdr_size:end] + area + image[end:]


def with_flags(image: bytes, flags: int) -> bytes:
    return image[:16] + struct.pack("<I", flags) + image[20:]


def test_tc_mcb_06_signed_only_with_a_signature_tlv():
    info = mcuboot().image_info
    sha = (0x10, bytes(32))
    assert info(FIXTURE).signed is False  # hash TLV only
    assert info(FIXTURE).encrypted is False
    assert info(with_tlv_area(FIXTURE, [sha])).signed is False
    for sig_type in (0x20, 0x22, 0x23, 0x24):  # RSA2048, ECDSASIG, RSA3072, ED25519
        signed = info(with_tlv_area(FIXTURE, [sha, (sig_type, bytes(64))]))
        assert signed.signed is True
        assert signed.encrypted is False
    # "The TLV areas": a signature TLV counts in the protected area too.
    sec_cnt = (0x50, struct.pack("<I", 7))
    in_protected = info(with_protected_area(FIXTURE, [sec_cnt, (0x22, bytes(64))]))
    assert (in_protected.signed, in_protected.encrypted) == (True, False)
    counter_only = info(with_protected_area(FIXTURE, [sec_cnt]))
    assert (counter_only.signed, counter_only.encrypted) == (False, False)
    assert 0x50 in counter_only.tlv_types  # the protected area was read


def test_tc_mcb_07_encrypted_follows_the_flag_bits():
    info = mcuboot().image_info
    assert info(FIXTURE).encrypted is False
    assert info(with_flags(FIXTURE, 0x4)).encrypted is True  # AES128
    assert info(with_flags(FIXTURE, 0x8)).encrypted is True  # AES256
    assert info(with_flags(FIXTURE, 0x1 | 0x20)).encrypted is False  # PIC, RAM_LOAD


PROTECTED = (INPUTS["mcuboot"] / "protected.bin").read_bytes()


def test_tc_mcb_03_protected_tlvs_without_their_magic_are_not_claimed():
    hdr_size, prot_size, img_size = struct.unpack_from("<HHI", PROTECTED, 8)
    assert prot_size  # the fixture has a protected TLV area
    info = mcuboot().image_info(PROTECTED)
    assert info.end == len(PROTECTED)
    assert 0x50 in info.tlv_types  # SEC_CNT, from the protected area

    at = hdr_size + img_size  # where 0x6908 must be
    assert PROTECTED[at : at + 2] == struct.pack("<H", 0x6908)
    corrupted = PROTECTED[:at] + struct.pack("<H", 0x6907) + PROTECTED[at + 2 :]
    with pytest.raises(InvalidInputFormat):
        mcuboot().image_info(corrupted)


def test_tc_mcb_04_extractor_writes_header_image_tlv(tmp_path: Path):
    source = tmp_path / "standard.bin"
    source.write_bytes(FIXTURE)
    out = tmp_path / "out"
    out.mkdir()
    mcuboot().MCUbootExtractor().extract(source, out)
    assert sorted(p.name for p in out.iterdir()) == [
        "header.bin",
        "image.bin",
        "tlv.bin",
    ]
    header, image, tlv = (
        (out / name).read_bytes() for name in ("header.bin", "image.bin", "tlv.bin")
    )
    # Must NOT: header bytes inside image.bin.
    (header_size,) = struct.unpack_from("<H", FIXTURE, 8)
    assert len(header) == header_size
    assert header + image + tlv == FIXTURE
