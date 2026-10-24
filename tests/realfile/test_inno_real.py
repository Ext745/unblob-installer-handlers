"""Inno Setup against real signed vendor installers (FSD FR-INNO-04, FR-PE-01)."""

import shutil
import subprocess
from pathlib import Path

import pytest
from unblob.report import ChunkReport, UnknownChunkReport

from tests.conftest import run_unblob

NAVX = Path("inno/navx-mxp-setup.exe")
IMAGER = Path("inno/imager-v2.0.12.exe")


def top_level(result, source: Path) -> list:
    return [
        r
        for t in result.results
        if t.task.path == source
        for r in t.reports
        if isinstance(r, ChunkReport | UnknownChunkReport)
    ]


@pytest.mark.xfail(reason="FR-PE-01: inno handler absent", strict=True)
@pytest.mark.parametrize("installer", [NAVX, IMAGER], ids=["navx", "imager"])
def test_tc_pe_01_signed_installer_chunk_includes_certificate(
    realfiles: Path, tmp_path: Path, installer: Path
):
    source = realfiles / installer
    reports = top_level(run_unblob(source, tmp_path, max_depth=1), source)
    # Must NOT: the certificate table reported as an unknown chunk.
    assert [
        (
            type(r).__name__,
            getattr(r, "handler_name", None),
            r.start_offset,
            r.end_offset,
        )
        for r in reports
    ] == [("ChunkReport", "inno", 0, source.stat().st_size)]


@pytest.mark.xfail(reason="FR-INNO-04: inno handler absent", strict=True)
def test_tc_inno_04_real_installers(realfiles: Path, tmp_path: Path):
    innoextract = shutil.which("innoextract")
    if innoextract is None:
        pytest.skip("precondition unmet: innoextract (extractors) not installed")

    run_unblob(realfiles / NAVX, tmp_path / "navx", max_depth=1)
    for name in ("navx2-mxp_4.0.447.hex", "navx-mxp_3.1.413.hex"):
        assert list((tmp_path / "navx").rglob(name)), name

    oracle = tmp_path / "oracle"
    subprocess.run(
        [innoextract, "-e", "-s", "-d", str(oracle), str(realfiles / IMAGER)],
        check=True,
    )
    run_unblob(realfiles / IMAGER, tmp_path / "imager", max_depth=1)
    (out,) = [p for p in (tmp_path / "imager").iterdir() if p.is_dir()]
    expected = sorted(
        str(p.relative_to(oracle)) for p in oracle.rglob("*") if p.is_file()
    )
    found = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    assert found == expected
