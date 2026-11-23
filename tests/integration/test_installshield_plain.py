"""InstallShield plain-layout setup.exe run by unblob (FSD §13a), Wave 1.

Fixtures: tests/integration/executable/installshield_plain/__input__, written
by tests/installshield_plain_image.py from FSD §13a.1 (not from the handler):
a minimal PE (image end 0x400) followed by an ANSI or a UTF-16 plain package
of three files.
"""

import hashlib
import random
from pathlib import Path

import pytest
from unblob.report import UnknownChunkReport

from tests.conftest import INPUTS, chunks, run_unblob
from tests.installshield_plain_image import files, minimal_pe, with_certificate

FIXTURES = ["ansi.exe", "utf16.exe"]
NAME = "installshield_plain"


def fixture(name: str) -> bytes:
    return (INPUTS[NAME] / name).read_bytes()


def spans(result, name: str = NAME) -> list[tuple[int, int]]:
    return [
        (c.start_offset, c.end_offset) for c in chunks(result) if c.handler_name == name
    ]


def unknown(result, sample: Path) -> list[tuple[int, int]]:
    return [
        (r.start_offset, r.end_offset)
        for t in result.results
        if t.task.path == sample
        for r in t.reports
        if isinstance(r, UnknownChunkReport)
    ]


@pytest.mark.parametrize("name", FIXTURES)
def test_tc_isw_07_found_at_the_mz(name: str, tmp_path: Path):
    exe = fixture(name)
    rng = random.Random(1807)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "embedded.bin"
    sample.write_bytes(rng.randbytes(0x1000) + exe + rng.randbytes(0x100))
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    # Must NOT: a chunk at the overlay, or one taking the bytes before 0x1000.
    assert spans(result) == [(0x1000, 0x1000 + len(exe))]


def test_tc_isw_09_appended_bytes_not_absorbed(tmp_path: Path):
    exe = fixture("ansi.exe")
    rng = random.Random(1809)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "trailing.exe"
    sample.write_bytes(exe + rng.randbytes(4096))
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    assert spans(result) == [(0, len(exe))]
    assert unknown(result, sample) == [(len(exe), len(exe) + 4096)]


@pytest.mark.parametrize(
    "gap, absorbed",
    [(bytes(5), True), (bytes(8), False), (b"\0\0\x01", False)],
    ids=["5-zero-bytes", "8-zero-bytes", "non-zero-byte"],
)
def test_tc_isw_09_certificate_table_after_alignment(
    gap: bytes, absorbed: bool, tmp_path: Path
):
    exe = fixture("ansi.exe")
    certificate = bytes(range(256)) * 4
    signed = with_certificate(exe, gap, certificate)
    sample = tmp_path / "signed.exe"
    sample.write_bytes(signed)
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    if absorbed:
        assert spans(result) == [(0, len(signed))]
        assert unknown(result, sample) == []
    else:
        assert spans(result) == [(0, len(exe))]
        assert unknown(result, sample) == [(len(exe), len(signed))]


@pytest.mark.parametrize("name", FIXTURES)
def test_tc_isw_10_files_under_their_destination(
    name: str, payload: bytes, tmp_path: Path
):
    sample = tmp_path / name
    sample.write_bytes(fixture(name))
    run_unblob(sample, tmp_path / "x", max_depth=1)
    out = next((tmp_path / "x").rglob(f"{name}_extract"))
    written = {
        str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob("*")
        if p.is_file()
    }
    assert written == {
        destination.replace("\\", "/"): hashlib.sha256(data).hexdigest()
        for _, destination, _, data in files(payload)
    }


# The other installers' fixtures, and the handler that keeps its chunk on each.
OTHERS = {
    "inno": "inno",
    "burn": "wix_burn",
    "nsis": "nsis",
    "installshield_setup": "installshield_setup",
}
OTHER_INPUTS = [(key, path) for key in OTHERS for path in sorted(INPUTS[key].iterdir())]


def headered_setup_exe(package: bytes) -> bytes:
    """Put a headered package after a real PE stub, as TC-ISW-01 builds it."""
    nsis = (INPUTS["nsis"] / "standard.exe").read_bytes()
    return nsis[: nsis.index(b"\xef\xbe\xad\xdeNullsoftInst") - 4] + package


@pytest.mark.parametrize(
    "key, source", OTHER_INPUTS, ids=[f"{k}-{p.name}" for k, p in OTHER_INPUTS]
)
def test_tc_isw_12_other_installers_not_claimed(key: str, source: Path, tmp_path: Path):
    sample = tmp_path / f"{source.name}.exe"
    data = source.read_bytes()
    sample.write_bytes(
        headered_setup_exe(data) if key == "installshield_setup" else data
    )
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    assert spans(result) == []
    # Must NOT: the other handler losing its chunk on the same file.
    assert OTHERS[key] in [c.handler_name for c in chunks(result)]


def test_tc_isw_12_pe_without_overlay_not_claimed(tmp_path: Path):
    sample = tmp_path / "bare.exe"
    sample.write_bytes(bytes(minimal_pe()))
    assert spans(run_unblob(sample, tmp_path / "x", max_depth=1)) == []
