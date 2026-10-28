"""Setup Factory against the SF10 build in the real-file store (FSD §8, §17)."""

import hashlib
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import chunks, run_unblob, tree

SF10 = Path("setupfactory/setup-factory-10.4.0.0.exe")


def test_tc_sf_01_sf10_is_one_setup_factory_chunk(realfiles: Path, tmp_path: Path):
    source = realfiles / SF10
    found = chunks(run_unblob(source, tmp_path, max_depth=1))
    assert [(c.handler_name, c.start_offset, c.end_offset) for c in found] == [
        ("setup_factory", 0, source.stat().st_size)
    ]


def test_tc_sf_03_sf10_extraction_equals_sfextract(
    realfiles: Path, tmp_path: Path, payload: bytes
):
    sfextract = shutil.which("sfextract")
    if sfextract is None:
        pytest.skip("precondition unmet: sfextract not installed")
    oracle = tmp_path / "oracle"
    # sfextract exits 0 when it finds no extractor; judge it by what it wrote.
    subprocess.run([sfextract, "-o", str(oracle), str(realfiles / SF10)], check=True)
    if not (oracle / "%AppFolder%" / "firmware.bin").is_file():
        pytest.skip("precondition unmet: sfextract has no Setup Factory 10 support")

    run_unblob(realfiles / SF10, tmp_path / "x", max_depth=1)
    (out,) = [p for p in (tmp_path / "x").iterdir() if p.is_dir()]

    assert tree(out) == tree(oracle)
    assert (out / "%AppFolder%" / "firmware.bin").read_bytes() == payload


def test_tc_pe_03_appended_bytes_not_absorbed(realfiles: Path, tmp_path: Path):
    installer = (realfiles / SF10).read_bytes()
    rng = random.Random(1703)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "padded.exe"
    sample.write_bytes(installer + rng.randbytes(4096))

    found = chunks(run_unblob(sample, tmp_path / "x", max_depth=1))

    assert [(c.handler_name, c.start_offset, c.end_offset) for c in found] == [
        ("setup_factory", 0, len(installer))
    ]


# Real installers from defactory's index (store: setupfactory/defactory-index).
INDEX = Path("setupfactory/defactory-index")


def check_matches_sfextract(realfiles: Path, tmp_path: Path, name: str) -> None:
    """One setup_factory chunk over the whole file, extracted as sfextract does."""
    source = realfiles / INDEX / name
    oracle = tmp_path / "oracle"
    run = subprocess.run(
        ["sfextract", "-o", str(oracle), str(source)], capture_output=True, check=False
    )
    assert run.returncode == 0, f"sfextract fails: {run.stderr[-300:]!r}"
    assert run.stdout.startswith(b"Extracted "), run.stdout[:200]

    found = chunks(run_unblob(source, tmp_path / "x", max_depth=1))
    assert [(c.handler_name, c.start_offset, c.end_offset) for c in found] == [
        ("setup_factory", 0, source.stat().st_size)
    ]
    (out,) = [p for p in (tmp_path / "x").iterdir() if p.is_dir()]
    assert tree(out) == tree(oracle)


@pytest.mark.parametrize(
    "name",
    [
        "sf8.2.1.0-Context_Menu_Enhancer.exe",
        "sf8.2.1.0-setup.exe",
        "sf9.0.2.0-setup.exe",
        "sf9.1.0.0-Decrap_Setup.exe",
    ],
)
def test_tc_sf_06_sf8_and_sf9_installers_equal_sfextract(
    realfiles: Path, tmp_path: Path, name: str
):
    check_matches_sfextract(realfiles, tmp_path, name)


def test_tc_sf_04_real_vendor_installer_equals_sfextract(
    realfiles: Path, tmp_path: Path
):
    name = "sf8.2.1.0-Context_Menu_Enhancer.exe"
    digest = hashlib.sha256((realfiles / INDEX / name).read_bytes()).hexdigest()
    manifest = (realfiles / "MANIFEST.sha256").read_text()
    assert f"{digest}  {INDEX / name}" in manifest  # the input, as recorded
    check_matches_sfextract(realfiles, tmp_path, name)


SF7 = ["sf7.0.1.0-ycs.exe", "sf7.0.3.0-setup365dni.exe", "sf7.0.6.1-FLVPlayerSetup.exe"]


@pytest.mark.parametrize("name", SF7)
def test_tc_sf_10_sf7_is_one_setup_factory_chunk(
    realfiles: Path, tmp_path: Path, name: str
):
    source = realfiles / INDEX / name
    found = chunks(run_unblob(source, tmp_path / "x", max_depth=1))
    assert [(c.handler_name, c.start_offset, c.end_offset) for c in found] == [
        ("setup_factory", 0, source.stat().st_size)
    ]


def test_tc_sf_07_sf7_installer_equals_sfextract(realfiles: Path, tmp_path: Path):
    check_matches_sfextract(realfiles, tmp_path, "sf7.0.6.1-FLVPlayerSetup.exe")


@pytest.mark.parametrize("name", SF7[:2])
def test_tc_sf_11_early_sf7_installers_equal_sfextract(
    realfiles: Path, tmp_path: Path, name: str
):
    check_matches_sfextract(realfiles, tmp_path, name)


def test_tc_sf_08_sf8_1_installer_equals_sfextract(realfiles: Path, tmp_path: Path):
    check_matches_sfextract(realfiles, tmp_path, "sf8.1.1004.0-CSFireMonitor3Setup.exe")


def test_tc_sf_09_sf9_2_installer_equals_sfextract(realfiles: Path, tmp_path: Path):
    check_matches_sfextract(realfiles, tmp_path, "sf9.2.0.0-cleanmem_setup.exe")
