"""Setup Factory against the SF10 build in the real-file store (FSD §8, FR-SF-01/03)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import chunks, run_unblob, tree

SF10 = Path("setupfactory/setup-factory-10.4.0.0.exe")


@pytest.mark.xfail(strict=True, reason="FR-SF-01: setup_factory handler absent")
def test_tc_sf_01_sf10_is_one_setup_factory_chunk(realfiles: Path, tmp_path: Path):
    source = realfiles / SF10
    found = chunks(run_unblob(source, tmp_path, max_depth=1))
    assert [(c.handler_name, c.start_offset, c.end_offset) for c in found] == [
        ("setup_factory", 0, source.stat().st_size)
    ]


@pytest.mark.xfail(strict=True, reason="FR-SF-03: setup_factory handler absent")
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
