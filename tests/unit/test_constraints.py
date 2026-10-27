"""Constraints checked from the repository itself (FSD §20, §21)."""

import importlib.metadata
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
BIN = Path(sys.executable).parent  # the environment under test
FIXTURES = ROOT / "tests" / "fixtures"
SOURCES = (FIXTURES / "SOURCES.md").read_text()
MIB = 1024 * 1024


def committed_fixtures() -> list[Path]:
    """List the fixture files themselves: tests/fixtures/<format>/<file>."""
    return sorted(p for p in FIXTURES.glob("*/*") if p.is_file())


def progress_rows() -> dict[str, list[str]]:
    """PLAN.md's progress table: handler -> its remaining cells."""
    plan = (ROOT / "PLAN.md").read_text()
    table = plan.split("## Progress", 1)[1].split("\n\n", 2)[1]
    rows = [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in table.splitlines()[2:]
        if line.startswith("|")
    ]
    return {row[0]: row[1:] for row in rows}


def test_tc_con_03_entry_point_registered():
    (entry,) = importlib.metadata.entry_points(group="unblob_v1", name="installers")
    assert entry.value == "unblob_installers"


def test_tc_con_05_ruff_and_pyright_clean_on_src():
    src = str(ROOT / "src")
    subprocess.run([BIN / "ruff", "check", src], check=True, cwd=ROOT)
    subprocess.run(
        [BIN / "pyright", "--pythonpath", sys.executable, src], check=True, cwd=ROOT
    )


def test_tc_con_06_mit_licence_and_no_gpl_source():
    assert (ROOT / "LICENSE").read_text().startswith("MIT License")
    markers = re.compile(
        rb"GNU (Lesser )?General Public License|SPDX-License-Identifier: [LA]?GPL|UniExtract|\.au3\b"
    )
    hits = [
        str(p.relative_to(ROOT))
        for p in (ROOT / "src").rglob("*.py")
        if markers.search(p.read_bytes())
    ]
    assert hits == []


@pytest.mark.xfail(strict=True, reason="FSD Phase 4: upstream PRs not opened yet")
def test_tc_con_07_every_handler_merged_or_in_review():
    rows = progress_rows()
    assert rows
    missing = [name for name, cells in rows.items() if not (cells[2] or cells[3])]
    assert missing == []


def test_tc_con_11_sfextract_pr_recorded():
    rows = progress_rows()
    assert "github.com/CybercentreCanada/sfextract/pull/" in " ".join(
        rows["Setup Factory"]
    )


def test_tc_con_08_every_fixture_has_a_source_record():
    unrecorded = [
        str(p.relative_to(FIXTURES))
        for p in committed_fixtures()
        if f"`{p.relative_to(FIXTURES)}`" not in SOURCES
    ]
    assert unrecorded == []


def test_tc_con_10_fixtures_over_1_mib_are_listed_exceptions():
    exceptions = SOURCES.split("## Size exceptions", 1)[1].split("\n## ", 1)[0]
    oversized = [
        str(p.relative_to(FIXTURES))
        for p in committed_fixtures()
        if p.stat().st_size > MIB and f"`{p.relative_to(FIXTURES)}`" not in exceptions
    ]
    assert oversized == []


@pytest.mark.xfail(
    strict=True,
    reason="FSD Phase 4: fixtures not yet in unblob's __input__/__output__ layout",
)
def test_tc_con_09_fixtures_have_unblob_output_layout():
    inputs = list((ROOT / "tests" / "integration").rglob("__input__"))
    assert inputs
    assert [p for p in inputs if not (p.parent / "__output__").is_dir()] == []
    assert len(inputs) >= len({p.parent.name for p in committed_fixtures()})
