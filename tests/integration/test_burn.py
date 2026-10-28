"""WiX/Burn handler run by unblob (FSD §9)."""

import struct
from pathlib import Path

from unblob.report import ChunkReport

from tests.conftest import (
    BURN_NS,
    INPUTS,
    burn_container_file,
    burn_hash,
    burn_manifest,
    chunks,
    run_unblob,
)

FIXTURE = INPUTS["burn"] / "standard.exe"


def test_tc_burn_01_fixture_is_one_wix_burn_chunk(tmp_path: Path):
    found = chunks(run_unblob(FIXTURE, tmp_path, max_depth=1))
    assert [(c.handler_name, c.start_offset, c.end_offset) for c in found] == [
        ("wix_burn", 0, FIXTURE.stat().st_size)
    ]


def test_tc_burn_03_one_file_per_container(tmp_path: Path):
    run_unblob(FIXTURE, tmp_path, max_depth=1)
    (out,) = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert sorted(p.name for p in out.iterdir()) == ["a0.cab", "u0.cab"]


def test_tc_burn_04_containers_match_manifest_and_input(tmp_path: Path):
    source = FIXTURE.read_bytes()
    result = run_unblob(FIXTURE, tmp_path, max_depth=2)
    (out,) = [p for p in tmp_path.iterdir() if p.is_dir()]
    manifest = burn_manifest(out)

    for c in manifest.iter(f"{BURN_NS}Container"):
        data = (out / burn_container_file(manifest, c.get("Id"))).read_bytes()
        assert len(data) == int(c.attrib["FileSize"])
        assert burn_hash(data) == c.get("Hash")

    for name in ("u0.cab", "a0.cab"):
        path = out / name
        data = path.read_bytes()
        assert source.find(data) != -1, f"{name} is not a range of the input"
        (cab_size,) = struct.unpack_from("<I", data, 8)  # CFHEADER.cbCabinet
        assert cab_size == len(data), f"{name} is not exactly one cabinet"
        cab_chunks = [
            (r.handler_name, r.start_offset, r.end_offset)
            for t in result.results
            if t.task.path == path
            for r in t.reports
            if isinstance(r, ChunkReport)
        ]
        assert cab_chunks == [("cab", 0, len(data))], name
