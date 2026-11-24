"""One valid sample per handler, for the common-behaviour tests (FSD §17).

Committed fixtures where they exist; Setup Factory has none
(tests/fixtures/SOURCES.md, "Not sourced"), so its sample comes from the
real-file store and those tests run at the real-file tier. InstallShield has
both: the hand-built version 5 cabinet, and a real one in REAL.
"""

from pathlib import Path

from unblob.models import Handler

import unblob_installers
from tests.conftest import INPUTS

COMMITTED = {
    "uf2": INPUTS["uf2"] / "standard.uf2",
    "ihex": INPUTS["ihex"] / "standard.hex",
    "dfuse": INPUTS["dfuse"] / "standard.dfu",
    "mcuboot": INPUTS["mcuboot"] / "standard.bin",
    "installshield": INPUTS["installshield"] / "standard.cab",
    "inno": INPUTS["inno"] / "standard-5.6.1-unicode.exe",
    "wix_burn": INPUTS["burn"] / "standard.exe",
    # FSD Phase 6 (its exit asks FR-COM-01..06 for these handlers too)
    "zigbee_ota": INPUTS["zigbee_ota"] / "standard.ota",
    "gbl": INPUTS["gbl"] / "standard.gbl",
    "cyacd": INPUTS["cyacd"] / "standard.cyacd",
    "cyacd2": INPUTS["cyacd2"] / "standard.cyacd2",
    "nsis": INPUTS["nsis"] / "standard.exe",
    "installshield_setup": INPUTS["installshield_setup"] / "stream.pftw",
    "installshield_plain": INPUTS["installshield_plain"] / "ansi.exe",
}
REAL = {  # relative to the real-file store
    "installshield": Path("installshield/baldurs-gate-patch-1.1.4315/data1.cab"),
    "setup_factory": Path("setupfactory/setup-factory-10.4.0.0.exe"),
}

# A plain PE: NSIS's exehead stub with no installer data appended
# (nsis=3.10-2ubuntu2, pinned in .devcontainer/Dockerfile).
PLAIN_PE = Path("/usr/share/nsis/Stubs/zlib-x86-unicode")

# Handlers whose extractor runs an external command (FSD §16.1).
COMMANDS = {
    "inno": "innoextract",
    "installshield": "unshield",
    "setup_factory": "sfextract",
    "nsis": "7z",
}


def handler(name: str) -> Handler:
    (cls,) = [h for h in unblob_installers.HANDLERS if name == h.NAME]
    return cls()


# The bytes each handler's PATTERNS match (Intel HEX: one record start).
PATTERN_BYTES = {
    "uf2": bytes.fromhex("5546320A57515D9E"),
    "ihex": b":10000000",
    "dfuse": b"DfuSe\x01",
    "mcuboot": bytes.fromhex("3DB8F396"),
    "installshield": b"ISc(",
    "inno": b"MZ",
    "setup_factory": b"MZ",
    "wix_burn": b"MZ",
    "zigbee_ota": bytes.fromhex("1EF1EE0B0001"),
    "gbl": bytes.fromhex("EB17A6030800000000000003"),
    "cyacd": b"1E9602AA0000\n:",
    "cyacd2": b"01" + b"0" * 22 + b"\n@",
    # "4d 5a [58] ?? ?? 00 00": MZ, then e_lfanew's high half zero.
    "nsis": b"MZ" + bytes(62),
    "installshield_setup": b"InstallShield\x00",
    "installshield_plain": b"MZ" + bytes(62),
}
