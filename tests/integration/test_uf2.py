"""UF2 handler run by unblob (FSD §10)."""

import random
from pathlib import Path

from tests.conftest import FIXTURES, chunks, run_unblob

FIXTURE = FIXTURES / "uf2" / "standard.uf2"


def test_tc_uf2_02_chunk_is_exactly_the_blocks(tmp_path: Path):
    rng = random.Random(1002)  # noqa: S311 - fixed test data, not cryptography
    before, after = rng.randbytes(0x200), rng.randbytes(300)
    uf2 = FIXTURE.read_bytes()
    sample = tmp_path / "embedded.bin"
    sample.write_bytes(before + uf2 + after)

    found = [
        c for c in chunks(run_unblob(sample, tmp_path / "x")) if c.handler_name == "uf2"
    ]

    assert [(c.start_offset, c.end_offset) for c in found] == [
        (len(before), len(before) + len(uf2))
    ]


def test_tc_uf2_04_one_region_file_holds_the_payload(tmp_path: Path, payload: bytes):
    run_unblob(FIXTURE, tmp_path)

    regions = sorted(p for p in tmp_path.rglob("*.bin") if p.parent.name == "RP2040")
    assert [p.name for p in regions] == ["0x10000000.bin"]
    assert regions[0].read_bytes() == payload
