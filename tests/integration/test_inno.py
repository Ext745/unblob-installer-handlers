"""Inno Setup handler run by unblob (FSD §7, §17)."""

import random
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import INPUTS, chunks, run_unblob, tree
from tests.samples import PLAIN_PE

FIXTURES_INNO = sorted((INPUTS["inno"]).glob("standard-*.exe"))
IDS = [p.stem.removeprefix("standard-") for p in FIXTURES_INNO]


@pytest.mark.parametrize("fixture", FIXTURES_INNO, ids=IDS)
def test_tc_inno_01_fixture_is_one_inno_chunk(fixture: Path, tmp_path: Path):
    found = chunks(run_unblob(fixture, tmp_path, max_depth=1))
    assert [(c.handler_name, c.start_offset, c.end_offset) for c in found] == [
        ("inno", 0, fixture.stat().st_size)
    ]


@pytest.mark.parametrize("fixture", FIXTURES_INNO, ids=IDS)
def test_tc_inno_03_extraction_equals_innoextract(
    fixture: Path, tmp_path: Path, payload: bytes
):
    innoextract = shutil.which("innoextract")
    if innoextract is None:
        pytest.skip("precondition unmet: innoextract (extractors) not installed")
    oracle = tmp_path / "oracle"
    subprocess.run(
        [innoextract, "-e", "-s", "-d", str(oracle), str(fixture)], check=True
    )

    run_unblob(fixture, tmp_path / "x", max_depth=1)
    (out,) = [p for p in (tmp_path / "x").iterdir() if p.is_dir()]

    assert tree(out) == tree(oracle)
    assert (out / "app" / "firmware.bin").read_bytes() == payload


def test_tc_pe_02_appended_bytes_not_absorbed(tmp_path: Path):
    installer = (INPUTS["inno"] / "standard-6.1.2.exe").read_bytes()
    rng = random.Random(1702)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "padded.exe"
    sample.write_bytes(installer + rng.randbytes(4096))

    found = chunks(run_unblob(sample, tmp_path / "x", max_depth=1))

    assert [(c.handler_name, c.start_offset, c.end_offset) for c in found] == [
        ("inno", 0, len(installer))
    ]


@pytest.mark.parametrize(
    "sample", [PLAIN_PE, INPUTS["nsis"] / "standard.exe"], ids=["plain-pe", "nsis"]
)
def test_tc_inno_02_pe_without_inno_setup_data_not_claimed(
    sample: Path, tmp_path: Path
):
    if not sample.is_file():
        pytest.skip(f"precondition unmet: {sample} not installed")
    found = chunks(run_unblob(sample, tmp_path, max_depth=1))
    assert "inno" not in [c.handler_name for c in found]
