"""Shared test helpers: unblob runs with this package's handlers loaded."""

import os
from pathlib import Path

import pytest
from unblob.handlers import BUILTIN_HANDLERS
from unblob.models import ProcessResult
from unblob.processing import DEFAULT_DEPTH, ExtractionConfig, process_file
from unblob.report import ChunkReport

import unblob_installers

FIXTURES = Path(__file__).parent / "fixtures"


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
        max_depth=max_depth,
    )
    return process_file(config, path)


def chunks(result: ProcessResult) -> list[ChunkReport]:
    return [
        r for task in result.results for r in task.reports if isinstance(r, ChunkReport)
    ]
