"""Real InstallShield plain-layout installers (FSD §13a, FR-ISW-09/11/12).

From the real-file store (D-4, MANIFEST.yaml): Prolific PL2303 v1.20.0 (ANSI
plain, unsigned) and PL23XX v4.10.0 (UTF-16 plain, signed, one alignment
byte before the certificate table); the Setup Factory 10.4 build for
FR-ISW-12.
"""

import hashlib
from pathlib import Path

import pytest
from unblob.report import ChunkReport, MultiFileReport, UnknownChunkReport

from tests.conftest import chunks, run_unblob

V1200 = "installshield-setup/PL2303-Prolific_DriverInstaller_v1200.exe"
V41000 = "installshield-setup/PL23XX-M_LogoDriver_Setup_41000_20260716.exe"
SHA256 = {
    V1200: "111d35d221b83dbaa8b00debf77f9fc735918f58bc3c1d5de8ff5565a4127fbd",
    V41000: "1e603f1fbb11a61a3e37f3dd31892f57b83af689fb7ed9a244e7819d5d8160bd",
}
SETUP_FACTORY = "setupfactory/setup-factory-10.4.0.0.exe"


def top_level(result, source: Path) -> list[tuple[str, str | None, int, int]]:
    return [
        (
            type(r).__name__,
            getattr(r, "handler_name", None),
            r.start_offset,
            r.end_offset,
        )
        for t in result.results
        if t.task.path == source
        for r in t.reports
        if isinstance(r, ChunkReport | UnknownChunkReport)
    ]


@pytest.mark.parametrize("installer", [V1200, V41000], ids=["v1.20.0", "v4.10.0"])
def test_tc_isw_11_real_installers_files_and_set(
    realfiles: Path, tmp_path: Path, installer: str
):
    source = realfiles / installer
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SHA256[installer]
    result = run_unblob(source, tmp_path, max_depth=3)
    out = next(tmp_path.rglob(f"{source.name}_extract"))
    written = sorted(
        p.relative_to(out).as_posix()
        for p in out.rglob("*")
        if p.is_file() and "_extract" not in p.relative_to(out).as_posix()
    )
    assert len(written) == 10, written
    # Must NOT: `Disk1\` kept as part of a file name.
    assert not [name for name in written if "\\" in name]
    assert {"Disk1/data1.hdr", "Disk1/data1.cab"} <= set(written)
    # unblob's recursion extracts the InstallShield set in Disk1 (FR-ISC-04).
    (multi,) = [
        r
        for t in result.results
        for r in t.reports
        if isinstance(r, MultiFileReport) and r.handler_name == "installshield_set"
    ]
    assert multi.extraction_reports == []
    assert any(p.is_file() for p in tmp_path.rglob("data1_extract/**/*"))


def test_tc_isw_09_real_signed_installer_one_chunk(realfiles: Path, tmp_path: Path):
    source = realfiles / V41000
    result = run_unblob(source, tmp_path, max_depth=1)
    # Certificate table and its 1 alignment byte inside the chunk (FR-PE-01).
    assert top_level(result, source) == [
        ("ChunkReport", "installshield_plain", 0, source.stat().st_size)
    ]


def test_tc_isw_12_real_setup_factory_not_claimed(realfiles: Path, tmp_path: Path):
    result = run_unblob(realfiles / SETUP_FACTORY, tmp_path, max_depth=1)
    names = [c.handler_name for c in chunks(result)]
    assert "installshield_plain" not in names
    assert "setup_factory" in names
