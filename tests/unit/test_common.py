"""Common handler behaviour on the committed fixtures (FSD §17).

InstallShield and Setup Factory have no committed fixture: their FR-COM-01
and -02 checks are in tests/realfile/test_common_real.py.
"""

from pathlib import Path

import pytest
from unblob.models import ExtractError
from unblob.report import ExtractCommandFailedReport

from tests.common_checks import (
    check_chunk_calculation_contained,
    check_failed_extraction_raises,
    check_false_candidate_declined,
    failing_tool,
)
from tests.samples import COMMANDS, COMMITTED
from unblob_installers.installshield import UnshieldSetExtractor

PURE = [n for n in COMMITTED if n not in COMMANDS]  # extractors without a tool


@pytest.mark.parametrize("name", COMMITTED)
def test_tc_com_01_false_candidate_declined_scan_continues(name: str, tmp_path: Path):
    check_false_candidate_declined(name, COMMITTED[name], tmp_path)


@pytest.mark.parametrize("name", COMMITTED)
def test_tc_com_02_only_invalid_input_format_escapes(name: str):
    check_chunk_calculation_contained(name, COMMITTED[name])


@pytest.mark.xfail(
    strict=True,
    reason="the feature is not implemented: extractors without a tool do not check their input is one whole chunk",
)
@pytest.mark.parametrize("name", PURE)
def test_tc_com_03_truncated_body_fails_extraction(name: str, tmp_path: Path):
    data = COMMITTED[name].read_bytes()
    # 100 bytes short cuts into the last block, record, element, TLV area or
    # container. (Inno is not here: innoextract recovers the whole payload
    # from half the fixture, so only a failing tool makes it fail.)
    keep = len(data) - 100
    truncated = tmp_path / f"truncated-{COMMITTED[name].name}"
    truncated.write_bytes(data[:keep])
    check_failed_extraction_raises(name, truncated, tmp_path)


@pytest.mark.parametrize("name", COMMANDS)
def test_tc_com_03_tool_exit_nonzero_fails_extraction(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    failing_tool(tmp_path / "bin", COMMANDS[name])
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{Path('/usr/bin')}:{Path('/bin')}")
    sample = tmp_path / "data1.cab"
    sample.write_bytes(b"input the stub never reads")
    check_failed_extraction_raises(name, sample, tmp_path)


def test_tc_com_03_set_tool_exit_nonzero_fails_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    failing_tool(tmp_path / "bin", "unshield")
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{Path('/usr/bin')}:{Path('/bin')}")
    volumes = []
    for n in (1, 2):
        volume = tmp_path / f"data{n}.cab"
        volume.write_bytes(b"input the stub never reads")
        volumes.append(volume)
    outdir = tmp_path / "out"
    outdir.mkdir()
    with pytest.raises(ExtractError) as raised:
        UnshieldSetExtractor().extract(volumes, outdir)
    assert any(isinstance(r, ExtractCommandFailedReport) for r in raised.value.reports)
