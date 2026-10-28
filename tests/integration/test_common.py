"""Common handler behaviour through unblob, on the committed fixtures (FSD §17)."""

import tempfile
from pathlib import Path

import pytest
from unblob.report import ChunkReport, ExtractorDependencyNotFoundReport

from tests.common_checks import path_without
from tests.conftest import run_unblob
from tests.samples import COMMITTED


def check_missing_tool_reported(
    name: str, tool: str, sample: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-COM-04: the chunk is still reported, with a dependency-not-found report."""
    monkeypatch.setenv("PATH", path_without(tool, tmp_path / "bin"))
    result = run_unblob(sample, tmp_path / "x", max_depth=1)
    reports = [
        r
        for t in result.results
        for r in t.reports
        if isinstance(r, ChunkReport) and r.handler_name == name
    ]
    assert len(reports) == 1, f"{name} chunks: {reports}"
    missing = [
        r
        for r in reports[0].extraction_reports
        if isinstance(r, ExtractorDependencyNotFoundReport)
    ]
    assert [m.dependencies for m in missing] == [[tool]], reports[0].extraction_reports


def check_output_contained(
    sample: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-COM-05: everything a run leaves behind is beneath the extraction directory."""
    inbox = tmp_path / "in"
    inbox.mkdir()
    source = inbox / sample.name
    source.write_bytes(sample.read_bytes())
    root = tmp_path / "tree"
    scratch = root / "tmp"  # the handlers' temporary directories land here
    scratch.mkdir(parents=True)
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    extract_root = root / "x"

    run_unblob(source, extract_root, max_depth=2)

    assert sorted(p.name for p in inbox.iterdir()) == [sample.name]
    assert sorted(p.name for p in root.iterdir()) == ["tmp", "x"]
    assert list(scratch.iterdir()) == [], "temporary files left behind"
    for path in extract_root.rglob("*"):
        if path.is_symlink():
            assert path.resolve().is_relative_to(extract_root.resolve()), path


@pytest.mark.xfail(
    strict=True,
    reason="the feature is not implemented: a missing tool raises FileNotFoundError, reported as UnknownError",
)
def test_tc_com_04_missing_innoextract_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    check_missing_tool_reported(
        "inno", "innoextract", COMMITTED["inno"], tmp_path, monkeypatch
    )


@pytest.mark.parametrize("name", COMMITTED)
def test_tc_com_05_output_only_beneath_extraction_dir(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    check_output_contained(COMMITTED[name], tmp_path, monkeypatch)
