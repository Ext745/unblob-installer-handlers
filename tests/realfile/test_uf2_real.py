"""UF2 against real board builds (FSD FR-UF2-09, FR-UF2-10)."""

from pathlib import Path

from tests.conftest import run_unblob
from tests.uf2image import payload_image


def region_files(root: Path, family: str) -> list[Path]:
    return sorted(p for p in root.rglob("*.bin") if p.parent.name == family)


def check_region(region: Path, uf2: Path, build_bin: Path) -> None:
    start, image = payload_image(uf2)
    build = build_bin.read_bytes()
    assert region.name == f"0x{start:08x}.bin"
    # The region is exactly what the UF2 writes, no byte invented ...
    assert region.read_bytes() == image
    # ... and equals the build over the build's length (the UF2 may pad its
    # last block beyond it).
    assert image[: len(build)] == build


def test_tc_uf2_09_pico_sdk_region_equals_build_bin(realfiles: Path, tmp_path: Path):
    d = realfiles / "boards" / "rp2040-pico-sdk"
    run_unblob(d / "uih_rp2040_hello.uf2", tmp_path)

    regions = region_files(tmp_path, "RP2040")
    assert len(regions) == 1
    check_region(regions[0], d / "uih_rp2040_hello.uf2", d / "uih_rp2040_hello.bin")


def test_tc_uf2_10_tinyuf2_region_equals_packed_bin(realfiles: Path, tmp_path: Path):
    d = realfiles / "boards" / "esp32s3-tinyuf2"
    run_unblob(d / "uih_esp32s3_hello.uf2", tmp_path)

    regions = region_files(tmp_path, "ESP32S3")
    assert len(regions) == 1
    check_region(regions[0], d / "uih_esp32s3_hello.uf2", d / "uih_esp32s3_hello.bin")
