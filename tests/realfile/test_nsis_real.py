"""The nsis handler on the real NSIS installers of the store (FSD §13b, FR-NSIS-07).

With only this package loaded (no #1255). The payload record is the one
FR-NSIS-01's method produced, kept in the store's MANIFEST.yaml
(fr_nsis_01_payload).
"""

import hashlib
from pathlib import Path

import pytest
import yaml
from unblob.report import ChunkReport, UnknownChunkReport

from tests.conftest import chunks, run_unblob
from tests.realfile.test_nsis_pr1255 import CASES


def payload_record(realfiles: Path, installer: str) -> dict:
    manifest = yaml.safe_load((realfiles / "MANIFEST.yaml").read_text())
    (entry,) = [f for f in manifest["files"] if f["path"] == installer]
    return entry["fr_nsis_01_payload"]


@pytest.mark.parametrize(
    "installer, payload", CASES, ids=["arduino", "rpiboot", "flip"]
)
def test_tc_nsis_07_real_installers_give_their_payload(
    realfiles: Path, tmp_path: Path, installer: str, payload: str
):
    source = realfiles / installer
    record = payload_record(realfiles, installer)
    assert record["path"] == payload
    result = run_unblob(source, tmp_path, max_depth=1)
    # Must NOT: the payload found only through another handler.
    top = [
        (
            type(r).__name__,
            getattr(r, "handler_name", None),
            r.start_offset,
            r.end_offset,
        )
        for t in result.results
        if t.task.path == source
        for r in t.reports
        if isinstance(r, ChunkReport | UnknownChunkReport)
    ]
    assert top == [("ChunkReport", "nsis", 0, source.stat().st_size)]
    (found,) = [
        p for p in tmp_path.rglob(Path(payload).name) if str(p).endswith(payload)
    ]
    assert hashlib.sha256(found.read_bytes()).hexdigest() == record["sha256"]


def test_tc_nsis_04_real_setup_factory_not_claimed(realfiles: Path, tmp_path: Path):
    source = realfiles / "setupfactory/setup-factory-10.4.0.0.exe"
    result = run_unblob(source, tmp_path, max_depth=1)
    assert [c.handler_name for c in chunks(result) if c.handler_name == "nsis"] == []
    assert any(c.handler_name == "setup_factory" for c in chunks(result))
