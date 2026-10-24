"""Acceptance of upstream PR #1255 on real NSIS installers (FSD FR-NSIS-01).

Runs only where the PR's handler is installed as a plugin (the devcontainer:
/opt/pr1255, FSD §15, D-1).
"""

import importlib.util
import sys
from pathlib import Path

import pytest
from unblob.handlers import BUILTIN_HANDLERS
from unblob.processing import ExtractionConfig, process_file
from unblob.report import ChunkReport

PR1255 = Path("/opt/pr1255/unblob_pr1255/__init__.py")

CASES = [
    # (installer in the store, a firmware file inside it)
    (
        "nsis/arduino-1.8.19-windows.exe",
        "hardware/arduino/avr/bootloaders/optiboot/optiboot_atmega328.hex",
    ),
    ("nsis/rpiboot_setup.exe", "msd/bootcode4.bin"),
    ("nsis/Flip Installer - 3.4.7.112.exe", "demo/Release/appli1.hex"),
]


def pr1255_handlers():
    if not PR1255.is_file():
        pytest.skip("precondition unmet: PR #1255 plugin (pr1255) not installed")
    spec = importlib.util.spec_from_file_location(
        "unblob_pr1255", PR1255, submodule_search_locations=[str(PR1255.parent)]
    )
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["unblob_pr1255"] = module
    spec.loader.exec_module(module)
    return module.unblob_register_handlers()


@pytest.mark.parametrize(
    "installer, payload", CASES, ids=["arduino", "rpiboot", "flip"]
)
def test_tc_nsis_01_pr1255_extracts_the_payload(
    realfiles: Path, tmp_path: Path, installer: str, payload: str
):
    config = ExtractionConfig(
        extract_root=tmp_path,
        randomness_depth=0,
        keep_extracted_chunks=True,
        handlers=(*BUILTIN_HANDLERS, *pr1255_handlers()),
        max_depth=1,  # the payload sits in the pe chunk's own extraction
    )
    source = realfiles / installer
    result = process_file(config, source)

    # Must NOT: count a payload another handler found as an NSIS pass. At the
    # installer's own level, the only chunk is PR #1255's pe.
    top = [r for r in result.results if r.task.path == source]
    top_chunks = [c for t in top for c in t.reports if isinstance(c, ChunkReport)]
    assert [c.handler_name for c in top_chunks] == ["pe"]
    assert [
        p for p in tmp_path.rglob(Path(payload).name) if str(p).endswith(payload)
    ], (
        installer,
        payload,
    )
