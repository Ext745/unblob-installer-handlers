"""Inno Setup against real signed vendor installers (FSD FR-INNO-04, FR-PE-01)."""

import random
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


@pytest.mark.parametrize("installer", [NAVX, IMAGER], ids=["navx", "imager"])
def test_tc_pe_01_signed_installer_chunk_includes_certificate(
    realfiles: Path, tmp_path: Path, installer: Path
):
    source = realfiles / installer
    reports = top_level(
        run_unblob(source, tmp_path, max_depth=1, pr1255="plugin"), source
    )
    # Must NOT: the certificate table reported as an unknown chunk, or a pe
    # chunk from #1255 beside or instead of ours.
    assert [
        (
            type(r).__name__,
            getattr(r, "handler_name", None),
            r.start_offset,
            r.end_offset,
        )
        for r in reports
    ] == [("ChunkReport", "inno", 0, source.stat().st_size)]


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


def test_tc_pe_04_signed_installer_with_appended_bytes(realfiles: Path, tmp_path: Path):
    # FR-PE-01's padded variant: the chunk ends at the certificate table's end,
    # not at the end of the file, so the appended bytes stay unknown.
    installer = (realfiles / NAVX).read_bytes()
    rng = random.Random(1704)  # noqa: S311 - fixed test data, not cryptography
    source = tmp_path / "padded.exe"
    source.write_bytes(installer + rng.randbytes(4096))

    reports = top_level(
        run_unblob(source, tmp_path / "x", max_depth=1, pr1255="plugin"), source
    )

    # unblob lists unknown chunks first; compare in file order.
    assert sorted(
        (
            r.start_offset,
            r.end_offset,
            type(r).__name__,
            getattr(r, "handler_name", None),
        )
        for r in reports
    ) == [
        (0, len(installer), "ChunkReport", "inno"),
        (len(installer), len(installer) + 4096, "UnknownChunkReport", None),
    ]
