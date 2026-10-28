"""Common handler behaviour for the handlers with no committed fixture (FSD §17).

InstallShield and Setup Factory, on samples from the real-file store; the
multi-volume set on the Avigo Manager set, packed in a tar as in TC-ISC-04.
"""

import tarfile
from pathlib import Path

import pytest
from unblob.report import ExtractorDependencyNotFoundReport, MultiFileReport

from tests.common_checks import (
    check_chunk_calculation_contained,
    check_false_candidate_declined,
    path_without,
)
from tests.conftest import run_unblob
from tests.integration.test_common import (
    check_missing_tool_reported,
    check_output_contained,
)
from tests.samples import COMMANDS, REAL

AVIGO = Path("installshield/avigomanager")


def avigo_tar(realfiles: Path, tmp_path: Path) -> Path:
    path = tmp_path / "avigo.tar"
    with tarfile.open(path, "w") as tar:
        for volume in sorted((realfiles / AVIGO).glob("data*.cab")):
            tar.add(volume, arcname=f"set/{volume.name}")
    return path


@pytest.mark.parametrize("name", REAL)
def test_tc_com_01_real_false_candidate_declined(
    name: str, realfiles: Path, tmp_path: Path
):
    check_false_candidate_declined(name, realfiles / REAL[name], tmp_path)


@pytest.mark.parametrize("name", REAL)
def test_tc_com_02_real_only_invalid_input_format_escapes(name: str, realfiles: Path):
    check_chunk_calculation_contained(name, realfiles / REAL[name])


@pytest.mark.xfail(
    strict=True,
    reason="the feature is not implemented: a missing tool raises FileNotFoundError, reported as UnknownError",
)
@pytest.mark.parametrize("name", REAL)
def test_tc_com_04_real_missing_tool_reported(
    name: str, realfiles: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    check_missing_tool_reported(
        name, COMMANDS[name], realfiles / REAL[name], tmp_path, monkeypatch
    )


@pytest.mark.parametrize("name", REAL)
def test_tc_com_05_real_output_only_beneath_extraction_dir(
    name: str, realfiles: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    check_output_contained(realfiles / REAL[name], tmp_path, monkeypatch)


def test_tc_com_05_real_set_output_only_beneath_extraction_dir(
    realfiles: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    check_output_contained(avigo_tar(realfiles, tmp_path), tmp_path, monkeypatch)


@pytest.mark.xfail(
    strict=True,
    reason="the feature is not implemented: a missing tool raises FileNotFoundError, reported as UnknownError",
)
def test_tc_com_04_real_set_missing_tool_reported(
    realfiles: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PATH", path_without("unshield", tmp_path / "bin"))
    result = run_unblob(avigo_tar(realfiles, tmp_path), tmp_path / "x", max_depth=2)
    (multi,) = [
        r
        for t in result.results
        for r in t.reports
        if isinstance(r, MultiFileReport) and r.handler_name == "installshield_set"
    ]
    missing = [
        r
        for r in multi.extraction_reports
        if isinstance(r, ExtractorDependencyNotFoundReport)
    ]
    assert [m.dependencies for m in missing] == [["unshield"]], multi.extraction_reports
