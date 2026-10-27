"""InstallShield against a real self-contained cabinet (FSD §6).

The Baldur's Gate patch 1.1.4315 data1.cab, with unshield's own md5 list as
the oracle (the handler itself runs unshield, so its output is not the oracle).
"""

import hashlib
import random
import shutil
import tarfile
from pathlib import Path

import pytest
from unblob.report import ExtractCommandFailedReport, MultiFileReport

from tests.conftest import chunks, run_unblob

CAB = Path("installshield/baldurs-gate-patch-1.1.4315/data1.cab")
MD5 = Path("installshield/baldurs-gate-patch-1.1.4315/expected.md5")


def isc_chunks(result):
    return [c for c in chunks(result) if c.handler_name == "installshield"]


def test_tc_isc_01_found_at_its_offset(realfiles: Path, tmp_path: Path):
    cab = (realfiles / CAB).read_bytes()
    rng = random.Random(601)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "embedded.bin"
    sample.write_bytes(rng.randbytes(0x1000) + cab)

    assert [
        c.start_offset
        for c in isc_chunks(run_unblob(realfiles / CAB, tmp_path / "a", max_depth=1))
    ] == [0]
    assert [
        c.start_offset
        for c in isc_chunks(run_unblob(sample, tmp_path / "b", max_depth=1))
    ] == [0x1000]


def test_tc_isc_02_chunk_ends_at_the_cabinet_end(realfiles: Path, tmp_path: Path):
    cab = (realfiles / CAB).read_bytes()
    rng = random.Random(602)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "trailing.bin"
    sample.write_bytes(cab + rng.randbytes(4096))

    result = run_unblob(sample, tmp_path / "x", max_depth=1)

    assert [(c.start_offset, c.end_offset) for c in isc_chunks(result)] == [
        (0, len(cab))
    ]


def test_tc_isc_03_all_files_match_the_md5_list(realfiles: Path, tmp_path: Path):
    if shutil.which("unshield") is None:
        pytest.skip("precondition unmet: unshield (extractors) not installed")
    # The cabinet's own files are the claim; recursing into them costs minutes.
    run_unblob(realfiles / CAB, tmp_path, max_depth=1)
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


AVIGO = Path("installshield/avigomanager")


def tar_of(path: Path, files: list[Path]) -> Path:
    with tarfile.open(path, "w") as tar:
        for f in files:
            tar.add(f, arcname=f"set/{f.name}")
    return path


def test_tc_isc_04_multi_volume_set_extracted_once(realfiles: Path, tmp_path: Path):
    if shutil.which("unshield") is None:
        pytest.skip("precondition unmet: unshield (extractors) not installed")
    volumes = sorted((realfiles / AVIGO).glob("data*.cab"))
    expected = {
        line.split(maxsplit=1)[1].removeprefix("./"): line.split()[0]
        for line in (realfiles / AVIGO / "expected.md5").read_text().splitlines()
        if line.strip()
    }

    # Directory handlers run on directories unblob extracts, as when a set is
    # unpacked from an installer: hand it the set inside a tar.
    run_unblob(tar_of(tmp_path / "complete.tar", volumes), tmp_path / "x", max_depth=2)
    (manager,) = list((tmp_path / "x").rglob("AvigoMgr.exe"))
    out = manager.parent.parent
    found = {
        str(p.relative_to(out)): hashlib.md5(p.read_bytes()).hexdigest()  # noqa: S324 - oracle is md5
        for p in out.rglob("*")
        if p.is_file()
    }
    assert found == expected  # every file once, nothing else

    # Must NOT: a set missing its last volume extracted partially as success.
    partial = tar_of(tmp_path / "partial.tar", volumes[:-1])
    result = run_unblob(partial, tmp_path / "y", max_depth=2)
    assert not list((tmp_path / "y").rglob("AvigoMgr.exe"))
    (multi,) = [
        r for t in result.results for r in t.reports if isinstance(r, MultiFileReport)
    ]
    assert multi.handler_name == "installshield_set"
    assert any(
        isinstance(r, ExtractCommandFailedReport) for r in multi.extraction_reports
    )
