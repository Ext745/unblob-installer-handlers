"""UF2 against real board builds (FSD FR-UF2-09, FR-UF2-10)."""

from pathlib import Path

import pytest

from tests.conftest import run_unblob


def region_files(root: Path, family: str) -> list[Path]:
    return sorted(p for p in root.rglob("*.bin") if p.parent.name == family)


@pytest.mark.xfail(reason="FR-UF2-09: uf2 handler absent", strict=True)
def test_tc_uf2_09_pico_sdk_region_equals_build_bin(realfiles: Path, tmp_path: Path):
    d = realfiles / "boards" / "rp2040-pico-sdk"
    run_unblob(d / "uih_rp2040_hello.uf2", tmp_path)

    regions = region_files(tmp_path, "RP2040")
    assert [p.name for p in regions] == ["0x10000000.bin"]
    assert regions[0].read_bytes() == (d / "uih_rp2040_hello.bin").read_bytes()


@pytest.mark.xfail(reason="FR-UF2-10: uf2 handler absent", strict=True)
def test_tc_uf2_10_tinyuf2_region_equals_packed_bin(realfiles: Path, tmp_path: Path):
    d = realfiles / "boards" / "esp32s3-tinyuf2"
    run_unblob(d / "uih_esp32s3_hello.uf2", tmp_path)

    regions = region_files(tmp_path, "ESP32S3")
    assert [p.name for p in regions] == ["0x00000000.bin"]
    assert regions[0].read_bytes() == (d / "uih_esp32s3_hello.bin").read_bytes()
