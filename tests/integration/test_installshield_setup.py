"""Headered InstallShield single-file packages run by unblob (FSD §13a), Wave 1.

Fixtures: tests/integration/archive/installshield_setup/__input__, written by
tests/installshield_setup_image.py from FSD §13a.1 (not from the handler).
"""

import hashlib
import random
from pathlib import Path

import pytest

from tests.conftest import INPUTS, chunks, run_unblob
from tests.installshield_setup_image import classic_members, stream_members

FIXTURES = {
    "classic.pftw": classic_members,
    "stream.pftw": stream_members,
    "stream4.pftw": stream_members,
}


def fixture(name: str) -> bytes:
    return (INPUTS["installshield_setup"] / name).read_bytes()


def pe_stub() -> bytes:
    """Return a real PE without an overlay: the NSIS fixture's exehead stub."""
    nsis = (INPUTS["nsis"] / "standard.exe").read_bytes()
    return nsis[: nsis.index(b"\xef\xbe\xad\xdeNullsoftInst") - 4]


def spans(result, name: str) -> list[tuple[int, int]]:
    return [
        (c.start_offset, c.end_offset) for c in chunks(result) if c.handler_name == name
    ]


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_tc_isw_01_found_at_the_signature(name: str, tmp_path: Path):
    package = fixture(name)
    rng = random.Random(1801)  # noqa: S311 - fixed test data, not cryptography
    stub = pe_stub()
    before = rng.randbytes(0x1000 - len(stub)) if len(stub) < 0x1000 else b""
    head = stub + before
    sample = tmp_path / "setup.exe"
    sample.write_bytes(head + package + rng.randbytes(0x100))
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    assert spans(result, "installshield_setup") == [
        (len(head), len(head) + len(package))
    ]


def test_tc_isw_02_chunk_ends_at_the_last_member(tmp_path: Path):
    package = fixture("classic.pftw")
    rng = random.Random(1802)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "trailing.bin"
    sample.write_bytes(package + rng.randbytes(4096))
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    assert spans(result, "installshield_setup") == [(0, len(package))]
    unknown = [
        (r.start_offset, r.end_offset)
        for t in result.results
        if t.task.path == sample
        for r in t.reports
        if r.__class__.__name__ == "UnknownChunkReport"
    ]
    assert unknown == [(len(package), len(package) + 4096)]


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_tc_isw_04_members_equal_the_built_content(
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
        m.name.replace("\\", "/"): hashlib.sha256(m.content).hexdigest()
        for m in FIXTURES[name](payload)
    }
