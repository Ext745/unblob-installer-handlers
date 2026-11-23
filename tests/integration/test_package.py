"""Package requirements needing an unblob process (FSD §5)."""

import contextlib
import subprocess
import sys
from pathlib import Path

import pytest
from unblob.file_utils import InvalidInputFormat
from unblob.models import DirectoryExtractor, ExtractError, File

import unblob_installers
from tests.conftest import INPUTS

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


# FSD §5: the handlers this package ships, by their documented names; not
# read from the package, so a handler it stops registering is missed here.
DOC_NAMES = [
    "UF2",
    "Intel HEX",
    "DfuSe",
    "MCUboot image",
    "InstallShield cabinet",
    "Inno Setup",
    "Setup Factory",
    "WiX Burn bundle",
    "InstallShield multi-volume set",
]


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
            str(INPUTS["uf2"] / "standard.uf2"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    assert '"handler_name": "uf2"' in (tmp_path / "r.json").read_text()

    # Every handler, not just the one that ran: each DOC appears in the
    # handler list unblob builds with -P and without the installed package.
    doc = tmp_path / "handlers.md"
    listing = subprocess.run(
        [
            sys.executable,
            "-c",
            NOT_INSTALLED,
            "-P",
            str(PACKAGE_DIR.parent),
            "--build-handlers-doc",
            str(doc),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert listing.returncode == 0, listing.stderr[-2000:]
    sections = doc.read_text()
    missing = [name for name in DOC_NAMES if f"\n## {name}\n" not in sections]
    assert missing == []


# FSD FR-PKG-05: the external commands the handlers rely on, by name.
FSD_COMMANDS = {"unshield", "innoextract", "sfextract", "7z"}


def listed_commands() -> set[str]:
    out = subprocess.run(
        [UNBLOB, "--show-external-dependencies"],
        capture_output=True,
        text=True,
        check=False,
    )
    rows = (line.split() for line in out.stdout.splitlines())
    return {row[0] for row in rows if len(row) == 2 and row[1] in ("✓", "✗")}


def test_tc_pkg_05_dependency_listing_covers_our_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    listed = listed_commands()
    assert listed >= FSD_COMMANDS, FSD_COMMANDS - listed

    # What the extractors actually run, observed rather than declared: each
    # one runs with subprocess.run recording the command and failing it.
    invoked = set()

    def record(command, *_args, **_kwargs):
        invoked.add(Path(command[0]).name)
        return subprocess.CompletedProcess(command, 3, b"", b"recorded")

    monkeypatch.setattr(subprocess, "run", record)
    sample = tmp_path / "data1.cab"
    sample.write_bytes(b"input the recorder never reads")
    for handler in [*unblob_installers.HANDLERS, *unblob_installers.DIR_HANDLERS]:
        out = tmp_path / handler.NAME
        extractor = handler.EXTRACTOR
        if extractor is None:
            # A per-chunk extractor (nsis, from #1255): run the chunk its
            # handler finds on its own fixture, so its tool is reached.
            (source,) = sorted(INPUTS[handler.NAME].iterdir())
            with File.from_path(source) as file:
                chunk = handler().calculate_chunk(file, 0)
            assert chunk is not None
            with contextlib.suppress(ExtractError, InvalidInputFormat):
                chunk.extract(source, out)
            continue
        out.mkdir()
        with contextlib.suppress(ExtractError, InvalidInputFormat):
            if isinstance(extractor, DirectoryExtractor):
                extractor.extract([sample], out)
            else:
                extractor.extract(sample, out)
    assert invoked  # the recorder saw the tool-running extractors
    assert invoked <= listed, invoked - listed
