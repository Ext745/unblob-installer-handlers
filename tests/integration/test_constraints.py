"""Constraints that need the installed environment and its tools (FSD §20)."""

import importlib.metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path

BIN = Path(sys.executable).parent  # the environment under test


def test_tc_con_01_unblob_pinned_to_26_6_4():
    assert importlib.metadata.version("unblob") == "26.6.4"
    requires = importlib.metadata.requires("unblob-installer-handlers") or []
    assert "unblob==26.6.4" in requires


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
    assert pin["vcs_info"]["commit_id"] == "ca5c3a65485f6c6c3731f81207e613e17a8f29f4"

    listing = output(str(BIN / "unblob"), "--show-external-dependencies")
    for tool in ("unshield", "innoextract", "sfextract", "7z"):
        assert f"    {tool} " in listing, tool
    assert "srec_cat" not in listing  # Intel HEX needs no external tool
