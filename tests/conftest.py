"""Shared test helpers: unblob runs with this package's handlers loaded."""

import hashlib
import os
from pathlib import Path

import pytest
from unblob.handlers import BUILTIN_DIR_HANDLERS, BUILTIN_HANDLERS
from unblob.models import ProcessResult
from unblob.processing import DEFAULT_DEPTH, ExtractionConfig, process_file
from unblob.report import ChunkReport

import unblob_installers

FIXTURES = Path(__file__).parent / "fixtures"
INTEGRATION = Path(__file__).parent / "integration"

# Committed fixtures, in unblob's integration layout (FSD C-09):
# tests/integration/<category>/<name>/__input__.
INPUTS = {
    "uf2": INTEGRATION / "archive" / "uf2" / "__input__",
    "ihex": INTEGRATION / "archive" / "ihex" / "__input__",
    "text-corpus": INTEGRATION / "archive" / "ihex" / "text-corpus" / "__input__",
    "dfuse": INTEGRATION / "archive" / "dfuse" / "__input__",
    "mcuboot": INTEGRATION / "archive" / "mcuboot" / "__input__",
    "installshield": INTEGRATION / "archive" / "installshield" / "__input__",
    "inno": INTEGRATION / "executable" / "inno" / "__input__",
    "burn": INTEGRATION / "executable" / "wix_burn" / "__input__",
    "nsis": INTEGRATION / "executable" / "nsis" / "__input__",
}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--realfiles",
        default=os.environ.get("REALFILES_DIR", "/srv/unblob-realfiles"),
        help="real-file store (FSD D-4); real-file and journey tests skip when absent",
    )


@pytest.fixture
def realfiles(request: pytest.FixtureRequest) -> Path:
    root = Path(str(request.config.getoption("--realfiles")))
    if not (root / "MANIFEST.sha256").is_file():
        pytest.skip(f"precondition unmet: no real-file store at {root}")
    return root


@pytest.fixture
def payload() -> bytes:
    return (FIXTURES / "payload.bin").read_bytes()


def run_unblob(
    path: Path, extract_root: Path, max_depth: int = DEFAULT_DEPTH
) -> ProcessResult:
    config = ExtractionConfig(
        extract_root=extract_root,
        randomness_depth=0,
        keep_extracted_chunks=True,
        handlers=(*BUILTIN_HANDLERS, *unblob_installers.HANDLERS),
        dir_handlers=(*BUILTIN_DIR_HANDLERS, *unblob_installers.DIR_HANDLERS),
        max_depth=max_depth,
    )
    return process_file(config, path)


def chunks(result: ProcessResult) -> list[ChunkReport]:
    return [
        r for task in result.results for r in task.reports if isinstance(r, ChunkReport)
    ]


def tree(root: Path) -> dict[str, str]:
    """Every file beneath root, relative path to SHA-256."""
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


BURN_NS = "{http://schemas.microsoft.com/wix/2008/Burn}"


def burn_manifest(extracted: Path):
    """Parse the bundle manifest (u0 member 0) beneath a Burn extraction directory."""
    import xml.etree.ElementTree as ET  # noqa: PLC0415 - Burn tests only

    return ET.parse(extracted / "u0.cab_extract" / "0").getroot()  # noqa: S314 - our fixture and a pinned real file


def burn_container_file(manifest, container_id: str | None) -> str:
    """Name the file FR-BURN-03 writes for a manifest Container id (None: UX)."""
    if container_id is None:
        return "u0.cab"
    for c in manifest.iter(f"{BURN_NS}Container"):
        if c.get("Id") == container_id:
            return f"a{int(c.get('AttachedIndex')) - 1}.cab"
    raise KeyError(container_id)


def burn_hash(data: bytes) -> str:
    """Burn's manifest Hash: upper-case hex SHA-1."""
    return hashlib.sha1(data, usedforsecurity=False).hexdigest().upper()
