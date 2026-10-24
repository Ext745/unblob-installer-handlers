"""DfuSe handler run by unblob (FSD §12)."""

import random
from pathlib import Path

from tests.conftest import FIXTURES, chunks, run_unblob

FIXTURE = FIXTURES / "dfuse" / "standard.dfu"


def test_tc_dfu_01_chunk_is_prefix_to_suffix(tmp_path: Path):
    rng = random.Random(1201)  # noqa: S311 - fixed test data, not cryptography
    before, after = rng.randbytes(0x400), rng.randbytes(500)
    dfu = FIXTURE.read_bytes()
    sample = tmp_path / "embedded.bin"
    sample.write_bytes(before + dfu + after)

    found = [
        c
        for c in chunks(run_unblob(sample, tmp_path / "x"))
        if c.handler_name == "dfuse"
    ]

    assert [(c.start_offset, c.end_offset) for c in found] == [
        (len(before), len(before) + len(dfu))
    ]


def test_tc_dfu_04_one_file_per_element(tmp_path: Path, payload: bytes):
    run_unblob(FIXTURE, tmp_path)

    elements = sorted(
        p for p in tmp_path.rglob("0x*.bin") if p.parent.name.startswith("target")
    )
    assert [f"{p.parent.name}/{p.name}" for p in elements] == [
        "target0_ST.../0x08000000.bin"
    ]
    assert elements[0].read_bytes() == payload
