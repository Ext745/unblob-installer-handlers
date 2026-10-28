"""InstallShield handler run by unblob on the hand-built cabinet (FSD §6)."""

import random
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import INPUTS, chunks, run_unblob, tree

FIXTURE = INPUTS["installshield"] / "standard.cab"


def test_tc_isc_08_fixture_cabinet_chunked_and_extracted_as_unshield_does(
    tmp_path: Path, payload: bytes
):
    cab = FIXTURE.read_bytes()
    rng = random.Random(608)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "embedded.bin"
    sample.write_bytes(rng.randbytes(0x1000) + cab + rng.randbytes(4096))

    # FR-ISC-01/02: found where it starts, ending at the cabinet's own end.
    found = [
        (c.start_offset, c.end_offset)
        for c in chunks(run_unblob(sample, tmp_path / "embedded", max_depth=1))
        if c.handler_name == "installshield"
    ]
    assert found == [(0x1000, 0x1000 + len(cab))]

    # FR-ISC-03: the same file set and bytes as unshield x on the same cabinet.
    unshield = shutil.which("unshield")
    if unshield is None:
        pytest.skip("precondition unmet: unshield (extractors) not installed")
    oracle = tmp_path / "oracle"
    shutil.copyfile(FIXTURE, tmp_path / "data1.cab")
    subprocess.run(
        [unshield, "-d", str(oracle), "x", str(tmp_path / "data1.cab")],
        check=True,
        capture_output=True,
    )
    run_unblob(FIXTURE, tmp_path / "x", max_depth=1)
    (out,) = [p for p in (tmp_path / "x").iterdir() if p.is_dir()]
    assert tree(out) == tree(oracle)
    assert (out / "Firmware" / "app" / "firmware.bin").read_bytes() == payload
