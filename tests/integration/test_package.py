"""Package requirements needing an unblob process (FSD §5)."""

import subprocess
import sys
from pathlib import Path

import unblob_installers
from tests.conftest import FIXTURES

PACKAGE_DIR = Path(unblob_installers.__file__).parent
# The unblob of the environment under test, never another one on PATH.
UNBLOB = str(Path(sys.executable).parent / "unblob")


# Seam for FR-PKG-02 ("package not installed"): hide our installed
# distribution from entry-point discovery, then run unblob's own CLI. Loading
# the package both ways makes pluggy refuse the second registration.
NOT_INSTALLED = """
import importlib.metadata as md, sys
_all = md.distributions
md.distributions = lambda **kw: [
    d for d in _all(**kw) if d.metadata["Name"] != "unblob-installer-handlers"
]
from unblob.cli import main
sys.argv = ["unblob", *sys.argv[1:]]
main()
"""


def test_tc_pkg_02_loads_with_plugins_path(tmp_path: Path):
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            NOT_INSTALLED,
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
