"""Constraints that need the installed environment and its tools (FSD §20)."""

import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BIN = Path(sys.executable).parent  # the environment under test
ROOT = Path(__file__).parents[2]
PY310 = Path("/opt/python3.10/bin/python3")  # pinned in .devcontainer/Dockerfile
WHEELS_310 = Path("/opt/wheels-py310")  # offline wheelhouse for it


FLOOR = "26.6.4"  # the oldest unblob the package supports (FSD C-01)


def tested_unblob() -> str:
    """The unblob version CI and releases test with: constraints.txt's pin."""
    pins = [
        line.split("==", 1)[1].strip()
        for line in (ROOT / "constraints.txt").read_text().splitlines()
        if line.startswith("unblob==")
    ]
    assert len(pins) == 1, pins
    return pins[0]


def as_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def test_tc_con_01_unblob_floor_and_tested_version():
    requires = importlib.metadata.requires("unblob-installer-handlers") or []
    assert f"unblob>={FLOOR}" in requires
    tested = tested_unblob()
    assert as_tuple(tested) >= as_tuple(FLOOR)
    # The environment under test runs the tested version, not whatever is newest.
    assert importlib.metadata.version("unblob") == tested


def output(*command: str) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.stdout + result.stderr


def test_tc_con_04_external_tools_are_the_pinned_versions():
    assert output("unshield", "-V").startswith("Unshield version 1.6.2.")
    assert output("innoextract", "--version").startswith(
        "innoextract 1.10-dev + 376a13e"
    )
    sfextract = shutil.which("sfextract")
    assert sfextract is not None
    tool_python = Path(sfextract).parent / "python"
    direct_url = output(
        str(tool_python),
        "-c",
        "import importlib.metadata as m; print(m.distribution('sfextract').read_text('direct_url.json'))",
    )
    pin = json.loads(direct_url)
    assert pin["url"] == "https://github.com/Ext745/sfextract"
    assert pin["vcs_info"]["commit_id"] == "33399fae02b0e462497bbcf75c51e24ccff15acc"

    listing = output(str(BIN / "unblob"), "--show-external-dependencies")
    for tool in ("unshield", "innoextract", "sfextract", "7z"):
        assert f"    {tool} " in listing, tool
    assert "srec_cat" not in listing  # Intel HEX needs no external tool


@pytest.mark.skipif(
    os.environ.get("UIH_PY310_RUN") == "1", reason="inside the 3.10 run it starts"
)
def test_tc_con_02_suites_pass_under_3_10_and_3_14(tmp_path: Path):
    # The 3.14 half is this run; the 3.10 half runs the same suites in a
    # fresh venv built offline from the image's wheelhouse.
    assert sys.version_info[:2] == (3, 14)
    if not PY310.is_file():
        pytest.skip("precondition unmet: no CPython 3.10 (python-3.10)")
    venv = tmp_path / "py310"
    subprocess.run([str(PY310), "-m", "venv", str(venv)], check=True)
    python = str(venv / "bin" / "python")
    install = [python, "-m", "pip", "install", "-q", "--no-index"]
    install += ["--find-links", str(WHEELS_310), "-c", str(ROOT / "constraints.txt")]
    install += ["-e", f"{ROOT}[dev]"]
    subprocess.run(install, check=True)
    suites = ["tests/unit", "tests/integration"]
    run = subprocess.run(
        [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *suites],
        cwd=ROOT,
        env={**os.environ, "UIH_PY310_RUN": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout[-4000:] + run.stderr[-2000:]
