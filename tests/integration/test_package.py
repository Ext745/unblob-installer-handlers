"""Package requirements needing an unblob process (FSD §5)."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import unblob_installers
from tests.conftest import FIXTURES

PACKAGE_DIR = Path(unblob_installers.__file__).parent
UNBLOB = shutil.which("unblob") or str(Path(sys.executable).parent / "unblob")


@pytest.mark.xfail(
    not unblob_installers.HANDLERS, reason="no handler registered yet", strict=True
)
def test_tc_pkg_02_loads_with_plugins_path(tmp_path: Path):
    # -P loads the package directory itself; the installed entry point is
    # disabled by running with a clean PYTHONPATH and the package not importable.
    out = subprocess.run(
        [
            UNBLOB,
            "-P",
            str(PACKAGE_DIR.parent),
            "-e",
            str(tmp_path / "x"),
            "--report",
            str(tmp_path / "r.json"),
            str(FIXTURES / "uf2" / "standard.uf2"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    assert '"handler_name": "uf2"' in (tmp_path / "r.json").read_text()


def test_tc_pkg_05_dependency_listing_covers_our_commands():
    out = subprocess.run(
        [UNBLOB, "--show-external-dependencies"],
        capture_output=True,
        text=True,
        check=False,
    )
    listed = out.stdout
    for handler in unblob_installers.HANDLERS:
        for command in handler.get_dependencies():
            assert command in listed, (handler.NAME, command)
