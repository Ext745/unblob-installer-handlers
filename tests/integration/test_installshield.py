"""InstallShield handler run by unblob on the hand-built cabinet (FSD §6)."""

import io
import random
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest
from unblob.report import ExtractionProblem, MultiFileReport

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


def test_tc_isc_09_fixture_set_extracted_once_from_hdr_and_cab(
    tmp_path: Path, payload: bytes
):
    # FR-ISC-04: a version 5 set unpacked from a tar is one installshield_set
    # extraction; neither file alone is an installshield chunk.
    if shutil.which("unshield") is None:
        pytest.skip("precondition unmet: unshield (extractors) not installed")
    result = run_unblob(INPUTS["installshield"] / "set.tar", tmp_path, max_depth=2)

    multi = [
        r
        for t in result.results
        for r in t.reports
        if isinstance(r, MultiFileReport) and r.handler_name == "installshield_set"
    ]
    assert len(multi) == 1
    assert multi[0].extraction_reports == []
    assert [c for c in chunks(result) if c.handler_name == "installshield"] == []
    (out,) = list(tmp_path.rglob("data1_extract"))
    assert sorted(tree(out)) == ["Firmware/app/firmware.bin", "Firmware/app/readme.txt"]
    assert (out / "Firmware" / "app" / "firmware.bin").read_bytes() == payload


# FR-ISC-08 / FR-ISC-09: a set with a gap or an invalid volume.
INCOMPLETE = {
    "data2-missing": {"data3.cab": None},  # None: a copy of data1.cab
    "data2-invalid": {"data2.cab": b"not an InstallShield cabinet".ljust(64, b"\0")},
}


def _incomplete_set(tmp_path: Path, extra: dict[str, bytes | None]) -> Path:
    with tarfile.open(INPUTS["installshield"] / "set.tar") as src:
        members = {}
        for member in src:
            content = src.extractfile(member)
            if content is not None:  # regular files only
                members[Path(member.name).name] = content.read()
    for name, data in extra.items():
        members[name] = members["data1.cab"] if data is None else data
    sample = tmp_path / "incomplete.tar"
    with tarfile.open(sample, "w", format=tarfile.USTAR_FORMAT) as tar:
        for name, data in sorted(members.items()):
            info = tarfile.TarInfo(f"set/{name}")
            info.size, info.mtime, info.mode = len(data), 0, 0o644
            tar.addfile(info, io.BytesIO(data))
    return sample


def _set_report(result) -> MultiFileReport:
    (multi,) = [
        r
        for t in result.results
        for r in t.reports
        if isinstance(r, MultiFileReport) and r.handler_name == "installshield_set"
    ]
    return multi


@pytest.mark.parametrize("extra", INCOMPLETE.values(), ids=INCOMPLETE.keys())
def test_tc_isc_12_every_volume_of_an_incomplete_set_taken(extra, tmp_path: Path):
    sample = _incomplete_set(tmp_path, extra)
    multi = _set_report(run_unblob(sample, tmp_path / "x", max_depth=2))
    volumes = {"data1.cab", *extra}
    assert volumes <= {p.name for p in multi.paths}


@pytest.mark.parametrize("extra", INCOMPLETE.values(), ids=INCOMPLETE.keys())
def test_tc_isc_13_incomplete_set_reported_without_files(extra, tmp_path: Path):
    if shutil.which("unshield") is None:
        pytest.skip("precondition unmet: unshield (extractors) not installed")
    sample = _incomplete_set(tmp_path, extra)
    multi = _set_report(run_unblob(sample, tmp_path / "x", max_depth=2))
    problems = [r for r in multi.extraction_reports if isinstance(r, ExtractionProblem)]
    assert any("data2.cab" in p.problem for p in problems)
    assert [
        p for p in (tmp_path / "x").rglob("data1_extract/**/*") if p.is_file()
    ] == []
