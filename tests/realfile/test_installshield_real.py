"""InstallShield against a real self-contained cabinet (FSD §6).

The Baldur's Gate patch 1.1.4315 data1.cab, with unshield's own md5 list as
the oracle (the handler itself runs unshield, so its output is not the oracle).
"""

import hashlib
import random
from pathlib import Path

import pytest

from tests.conftest import chunks, run_unblob

CAB = Path("installshield/baldurs-gate-patch-1.1.4315/data1.cab")
MD5 = Path("installshield/baldurs-gate-patch-1.1.4315/expected.md5")


def isc_chunks(result):
    return [c for c in chunks(result) if c.handler_name == "installshield"]


@pytest.mark.xfail(reason="FR-ISC-01: installshield handler absent", strict=True)
def test_tc_isc_01_found_at_its_offset(realfiles: Path, tmp_path: Path):
    cab = (realfiles / CAB).read_bytes()
    rng = random.Random(601)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "embedded.bin"
    sample.write_bytes(rng.randbytes(0x1000) + cab)

    assert [
        c.start_offset for c in isc_chunks(run_unblob(realfiles / CAB, tmp_path / "a"))
    ] == [0]
    assert [c.start_offset for c in isc_chunks(run_unblob(sample, tmp_path / "b"))] == [
        0x1000
    ]


@pytest.mark.xfail(reason="FR-ISC-02: installshield handler absent", strict=True)
def test_tc_isc_02_chunk_ends_at_the_cabinet_end(realfiles: Path, tmp_path: Path):
    cab = (realfiles / CAB).read_bytes()
    rng = random.Random(602)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "trailing.bin"
    sample.write_bytes(cab + rng.randbytes(4096))

    result = run_unblob(sample, tmp_path / "x")

    assert [(c.start_offset, c.end_offset) for c in isc_chunks(result)] == [
        (0, len(cab))
    ]


@pytest.mark.xfail(reason="FR-ISC-03/05: installshield handler absent", strict=True)
def test_tc_isc_03_all_files_match_the_md5_list(realfiles: Path, tmp_path: Path):
    run_unblob(realfiles / CAB, tmp_path)
    (out,) = [p for p in tmp_path.rglob("*_extract") if p.is_dir()][:1]
    expected = {
        line.split(maxsplit=1)[1].removeprefix("./"): line.split()[0]
        for line in (realfiles / MD5).read_text().splitlines()
        if line.strip()
    }
    found = {
        str(p.relative_to(out)): hashlib.md5(p.read_bytes()).hexdigest()  # noqa: S324 - oracle is md5
        for p in out.rglob("*")
        if p.is_file() and str(p.relative_to(out)) in expected
    }
    assert found == expected
