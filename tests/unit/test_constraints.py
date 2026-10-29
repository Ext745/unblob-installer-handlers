"""Constraints checked from the repository itself (FSD §20, §21)."""

import importlib.metadata
import re
import subprocess
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # Python 3.10 (C-02): pytest's own dependency
    import tomli as tomllib

ROOT = Path(__file__).parents[2]
BIN = Path(sys.executable).parent  # the environment under test
INTEGRATION = ROOT / "tests" / "integration"
SOURCES = (ROOT / "tests" / "fixtures" / "SOURCES.md").read_text()
MIB = 1024 * 1024


def committed_fixtures() -> list[Path]:
    """List the fixture files themselves: tests/integration/**/__input__/<file>."""
    return sorted(p for p in INTEGRATION.glob("**/__input__/*") if p.is_file())


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


def flat(table: dict, prefix: str = "") -> dict:
    out = {}
    for key, value in table.items():
        if isinstance(value, dict):
            out |= flat(value, f"{prefix}{key}.")
        else:
            out[f"{prefix}{key}"] = value
    return out


# The only places this repository's ruff/pyright settings may differ from
# unblob 26.6.4's, and why none of them weakens a check on src/:
ALLOWED_DIFFERENCES = {
    # paths that hold no package source
    "ruff.extend-exclude": [".claude"],
    "pyright.exclude": [".venv", "build", ".claude", ".devcontainer"],
    # first-party is this package, not unblob
    "ruff.lint.isort.known-first-party": ["unblob_installers"],
    # dropped: it exempted __init__.py from unused-import checks (stricter without)
    "ruff.lint.ignore-init-module-imports": None,
}


def test_tc_con_05_ruff_and_pyright_clean_on_src():
    upstream = tomllib.loads(
        (ROOT / "tests" / "data" / "unblob-26.6.4-lint.toml").read_text()
    )
    ours = tomllib.loads((ROOT / "pyproject.toml").read_text())
    theirs = flat({k: upstream["tool"][k] for k in ("ruff", "pyright")})
    mine = flat({k: ours["tool"][k] for k in ("ruff", "pyright")})
    differences = {
        key: mine.get(key)
        for key in theirs.keys() | mine.keys()
        if theirs.get(key) != mine.get(key)
    }
    assert differences == ALLOWED_DIFFERENCES  # no local override weakens them

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
    # A PR cell opens with the PR's URL; a merged cell is the unblob version.
    # Anything else ("not opened: ...", a bare "#1687") is not a link.
    pr = re.compile(r"https://github\.com/onekey-sec/unblob/pull/\d+\b")
    merged = re.compile(r"\d+\.\d+(\.\d+)?")
    missing = [
        name
        for name, cells in rows.items()
        if not (pr.match(cells[2]) or merged.fullmatch(cells[3]))
    ]
    assert missing == []


def test_tc_con_11_sfextract_pr_recorded():
    rows = progress_rows()
    assert "github.com/CybercentreCanada/sfextract/pull/" in " ".join(
        rows["Setup Factory"]
    )


def test_tc_con_08_every_fixture_has_a_source_record():
    unrecorded = [
        str(p.relative_to(INTEGRATION))
        for p in committed_fixtures()
        if f"`{p.relative_to(INTEGRATION)}`" not in SOURCES
    ]
    assert unrecorded == []


def test_tc_con_10_fixtures_over_1_mib_are_listed_exceptions():
    exceptions = SOURCES.split("## Size exceptions", 1)[1].split("\n## ", 1)[0]
    oversized = [
        str(p.relative_to(INTEGRATION))
        for p in committed_fixtures()
        if p.stat().st_size > MIB
        and f"`{p.relative_to(INTEGRATION)}`" not in exceptions
    ]
    assert oversized == []


def test_tc_con_09_fixtures_have_unblob_output_layout():
    inputs = list((ROOT / "tests" / "integration").rglob("__input__"))
    assert inputs
    assert [p for p in inputs if not (p.parent / "__output__").is_dir()] == []
    assert len(inputs) >= len({p.parent.name for p in committed_fixtures()})
