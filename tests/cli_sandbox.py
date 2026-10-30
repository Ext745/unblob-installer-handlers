"""The `unblob` command with its Landlock sandbox against process_file (FR-COM-06).

The command runs extraction in a sandbox that allows writes only beneath the
extraction root, /dev/shm and the log and report paths; process_file applies
none. A handler that writes elsewhere (a scratch copy in the system temp
directory, say) passes every process_file test and fails for every user.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import run_unblob, tree

UNBLOB = Path(sys.executable).with_name("unblob")  # the venv's, with the plugin

# Writes a file outside the one path the sandbox allows. Exit 0: Landlock
# blocked it. Exit 1: the write went through, so the kernel enforces nothing.
_PROBE = """
import sys, tempfile
from unblob._rust.sandbox import AccessFS, SandboxError, restrict_access
allowed = tempfile.mkdtemp()
try:
    restrict_access(AccessFS.read("/"), AccessFS.read_write(allowed))
except SandboxError:
    sys.exit(1)
try:
    open(sys.argv[1], "w").close()
except PermissionError:
    sys.exit(0)
sys.exit(1)
"""


def landlock_enforced(tmp_path: Path) -> bool:
    probe = subprocess.run(
        [sys.executable, "-I", "-c", _PROBE, str(tmp_path / "outside")], check=False
    )
    return probe.returncode == 0


def errors(report: Path) -> list[dict]:
    """Every entry in the CLI's JSON report with severity ERROR."""
    found: list[dict] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if node.get("severity") == "ERROR":
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(report.read_text()))
    return found


def check_cli_matches_api(path: Path, tmp_path: Path, max_depth: int = 1) -> None:
    if not landlock_enforced(tmp_path):
        pytest.skip("precondition unmet: the kernel does not enforce Landlock")
    env = {k: v for k, v in os.environ.items() if k != "TMPDIR"}
    cli, report = tmp_path / "cli", tmp_path / "report.json"
    subprocess.run(
        [
            str(UNBLOB),
            "-d", str(max_depth),
            "-n", "0",
            "-k",
            "-e", str(cli),
            "--report", str(report),
            "--log", str(tmp_path / "unblob.log"),
            str(path),
        ],
        env=env,
        capture_output=True,
        check=False,
    )  # fmt: skip
    assert errors(report) == []
    api = tmp_path / "api"
    run_unblob(path, api, max_depth=max_depth)
    assert tree(cli) == tree(api)
    assert tree(cli)
