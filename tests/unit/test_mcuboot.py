"""MCUboot pure core (FSD §13): signed and encrypted, from TLVs and flags."""

import importlib
import struct
from types import ModuleType

import pytest

from tests.conftest import FIXTURES

FIXTURE = (FIXTURES / "mcuboot" / "standard.bin").read_bytes()


def mcuboot() -> ModuleType:
    # Imported per test, so the file is collected before the module exists.
    return importlib.import_module("unblob_installers.mcuboot")


def with_tlv_area(image: bytes, tlvs: list[tuple[int, bytes]]) -> bytes:
    """Replace the fixture's TLV area with the given (type, value) TLVs."""
    hdr_size, prot_size, img_size = struct.unpack_from("<HHI", image, 8)
    body = image[: hdr_size + img_size + prot_size]
    entries = b"".join(struct.pack("<HH", t, len(v)) + v for t, v in tlvs)
    return body + struct.pack("<HH", 0x6907, 4 + len(entries)) + entries


def with_flags(image: bytes, flags: int) -> bytes:
    return image[:16] + struct.pack("<I", flags) + image[20:]


@pytest.mark.xfail(reason="FR-MCB-06: mcuboot handler absent", strict=True)
def test_tc_mcb_06_signed_only_with_a_signature_tlv():
    info = mcuboot().image_info
    sha = (0x10, bytes(32))
    assert info(FIXTURE).signed is False  # hash TLV only
    assert info(with_tlv_area(FIXTURE, [sha])).signed is False
    for sig_type in (0x20, 0x22, 0x23, 0x24):  # RSA2048, ECDSASIG, RSA3072, ED25519
        assert info(with_tlv_area(FIXTURE, [sha, (sig_type, bytes(64))])).signed is True


@pytest.mark.xfail(reason="FR-MCB-07: mcuboot handler absent", strict=True)
def test_tc_mcb_07_encrypted_follows_the_flag_bits():
    info = mcuboot().image_info
    assert info(FIXTURE).encrypted is False
    assert info(with_flags(FIXTURE, 0x4)).encrypted is True  # AES128
    assert info(with_flags(FIXTURE, 0x8)).encrypted is True  # AES256
    assert info(with_flags(FIXTURE, 0x1 | 0x20)).encrypted is False  # PIC, RAM_LOAD
