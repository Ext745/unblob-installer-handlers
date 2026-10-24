"""Intel HEX against a real Arduino build (FSD FR-HEX-08), with avr-objcopy as oracle."""

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import run_unblob

OPTIBOOT = Path("hex/optiboot_atmega328.hex")


def test_tc_hex_08_optiboot_regions_equal_avr_objcopy(realfiles: Path, tmp_path: Path):
    objcopy = shutil.which("avr-objcopy")
    if objcopy is None:
        pytest.skip("precondition unmet: avr-objcopy (oracles) not installed")
    hexfile = realfiles / OPTIBOOT
    oracle = tmp_path / "oracle.bin"
    subprocess.run(
        [objcopy, "-I", "ihex", "-O", "binary", str(hexfile), str(oracle)], check=True
    )
    # avr-objcopy's binary starts at the lowest data address and fills gaps.
    data_addresses = [
        int(line[3:7], 16)
        for line in hexfile.read_text().splitlines()
        if line[7:9] == "00"
    ]
    base = min(data_addresses)
    expected = oracle.read_bytes()

    run_unblob(hexfile, tmp_path / "x")

    regions = sorted((tmp_path / "x").rglob("0x*.bin"))
    assert regions, "no region file"
    for region in regions:
        address = int(region.stem, 16)
        data = region.read_bytes()
        assert data == expected[address - base : address - base + len(data)], (
            region.name
        )
    # Every data byte and nothing else: avr-objcopy fills gaps between regions,
    # the handler does not (FSD OD-1), so count the data records' bytes instead.
    data_bytes = sum(
        int(line[1:3], 16)
        for line in hexfile.read_text().splitlines()
        if line[7:9] == "00"
    )
    assert sum(r.stat().st_size for r in regions) == data_bytes
