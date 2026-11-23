"""NSIS installer handler run by unblob (FSD §13b), Wave 1.

Fixture: tests/integration/executable/nsis/__input__/standard.exe, built with
makensis from tests/fixtures/standard.nsi (installs the payload as
firmware.bin).
"""

import hashlib
import random
import subprocess
from pathlib import Path

import pytest

from tests.conftest import INPUTS, chunks, run_unblob

FIRSTHEADER_MAGIC = b"\xef\xbe\xad\xdeNullsoftInst"


def nsis_fixture() -> bytes:
    return (INPUTS["nsis"] / "standard.exe").read_bytes()


def firstheader_offset(installer: bytes) -> int:
    """Offset of the firstheader (flags precede the signature)."""
    offset = installer.index(FIRSTHEADER_MAGIC) - 4
    assert offset % 512 == 0
    return offset


def spans(result, name: str) -> list[tuple[int, int]]:
    return [
        (c.start_offset, c.end_offset) for c in chunks(result) if c.handler_name == name
    ]


def tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_tc_nsis_03_found_at_its_mz(tmp_path: Path):
    installer = nsis_fixture()
    sample = tmp_path / "standard.exe"
    sample.write_bytes(installer)
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    assert [(c.handler_name, c.start_offset, c.end_offset) for c in chunks(result)] == [
        ("nsis", 0, len(installer))
    ]


def test_tc_nsis_03_embedded_at_0x1000(tmp_path: Path):
    installer = nsis_fixture()
    rng = random.Random(1603)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "embedded.bin"
    sample.write_bytes(rng.randbytes(0x1000) + installer + rng.randbytes(0x100))
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    assert spans(result, "nsis") == [(0x1000, 0x1000 + len(installer))]
    assert spans(result, "pe") == []


def test_tc_nsis_04_stub_alone_not_claimed(tmp_path: Path):
    installer = nsis_fixture()
    sample = tmp_path / "stub.exe"
    sample.write_bytes(installer[: firstheader_offset(installer)])
    assert spans(run_unblob(sample, tmp_path / "x", max_depth=1), "nsis") == []


def test_tc_nsis_04_firstheader_512_later_not_claimed(tmp_path: Path):
    installer = nsis_fixture()
    at = firstheader_offset(installer)
    sample = tmp_path / "moved.exe"
    sample.write_bytes(installer[:at] + bytes(512) + installer[at:])
    assert spans(run_unblob(sample, tmp_path / "x", max_depth=1), "nsis") == []


@pytest.mark.parametrize(
    "handler,name",
    [
        ("inno", "standard-5.6.1-unicode.exe"),
        ("inno", "standard-6.1.2.exe"),
        ("inno", "standard-7.1.0.exe"),
        ("burn", "standard.exe"),
    ],
)
def test_tc_nsis_04_other_installers_not_claimed(
    handler: str, name: str, tmp_path: Path
):
    data = (INPUTS[handler] / name).read_bytes()
    sample = tmp_path / name
    sample.write_bytes(data)
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    assert spans(result, "nsis") == []
    own = "wix_burn" if handler == "burn" else handler
    assert spans(result, own) == [(0, len(data))]  # its own handler keeps it


def test_tc_nsis_06_same_files_as_7z(tmp_path: Path):
    sample = tmp_path / "standard.exe"
    sample.write_bytes(nsis_fixture())
    run_unblob(sample, tmp_path / "x", max_depth=1)
    ours = tree(next((tmp_path / "x").rglob("standard.exe_extract")))
    reference = tmp_path / "7z"
    subprocess.run(
        ["7z", "x", "-y", str(sample), f"-o{reference}"],
        check=True,
        capture_output=True,
    )
    assert ours == tree(reference)
    assert ours  # the installer's files, not an empty extraction


def test_tc_pe_02_nsis_appended_bytes_not_absorbed(tmp_path: Path):
    installer = nsis_fixture()
    rng = random.Random(1702)  # noqa: S311 - fixed test data, not cryptography
    sample = tmp_path / "padded.exe"
    sample.write_bytes(installer + rng.randbytes(4096))
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    assert spans(result, "nsis") == [(0, len(installer))]
