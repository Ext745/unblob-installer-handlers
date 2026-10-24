"""MCUboot against the real signed SLOT3 image, with imgtool as oracle (FR-MCB-09)."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import chunks, run_unblob

SIGNED = Path("boards/esp32-mcuboot/app.signed.bin")
SIGNATURE_TLVS = {"RSA2048", "ECDSASIG", "RSA3072", "ED25519"}
ENCRYPTED_FLAGS = {"ENCRYPTED_AES128", "ENCRYPTED_AES256"}


def field(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.M)
    assert match, pattern
    return match.group(1)


def dumpinfo(imgtool: str, image: Path) -> dict:
    out = subprocess.run(
        [imgtool, "dumpinfo", str(image)], capture_output=True, text=True, check=True
    ).stdout
    return {
        "version": field(r"^version:\s+(\S+)", out),
        "load_address": int(field(r"^load_addr:\s+(0x[0-9a-fA-F]+)", out), 16),
        "flags": int(field(r"^flags:\s+(0x[0-9a-fA-F]+)", out), 16),
        "tlv_names": set(re.findall(r"type:\s+(\w+)\s+\(0x", out)),
        "flag_names": set(
            re.findall(r"^\s+(\w+)\s*$", out.split("flags:")[1].split("\n\n")[0], re.M)
        ),
    }


@pytest.mark.xfail(reason="FR-MCB-09: mcuboot handler absent", strict=True)
def test_tc_mcb_09_report_equals_imgtool_dumpinfo(realfiles: Path, tmp_path: Path):
    imgtool = shutil.which("imgtool")
    if imgtool is None:
        pytest.skip("precondition unmet: imgtool (oracles) not installed")
    image = realfiles / SIGNED
    expected = dumpinfo(imgtool, image)

    (chunk,) = [
        c for c in chunks(run_unblob(image, tmp_path)) if c.handler_name == "mcuboot"
    ]
    (report,) = [
        r.model_dump()
        for r in chunk.extraction_reports
        if r.__typename__ == "MCUbootImageReport"
    ]

    assert report["version"] == expected["version"]
    assert report["load_address"] == expected["load_address"]
    assert report["flags"] == expected["flags"]
    assert report["signed"] == bool(expected["tlv_names"] & SIGNATURE_TLVS)
    assert report["signed"] is True  # this image is ECDSA-P256 signed
    assert report["encrypted"] == bool(expected["flag_names"] & ENCRYPTED_FLAGS)
