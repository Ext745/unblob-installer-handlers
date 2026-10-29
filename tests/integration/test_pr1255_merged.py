"""PE-based fixtures with PR #1255 merged into unblob (FSD §4.1 risk, §17).

Once #1255 is merged, its pe handler is one of unblob's own handlers, and
those always come before a plugin's. unblob keeps the first valid chunk at an
offset, so pe claims the whole installer and ours is never asked.
"""

from pathlib import Path

import pytest

from tests.conftest import INPUTS, chunks, run_unblob

CASES = [
    *((p, "inno") for p in sorted(INPUTS["inno"].glob("standard-*.exe"))),
    (INPUTS["burn"] / "standard.exe", "wix_burn"),
]


@pytest.mark.xfail(
    strict=True, reason="FSD §4.1: #1255's pe comes first once merged, claims the PE"
)
@pytest.mark.parametrize(
    "fixture, handler", CASES, ids=[f"{h}-{p.stem}" for p, h in CASES]
)
def test_tc_pe_05_merged_pr1255_leaves_installers_to_us(
    fixture: Path, handler: str, tmp_path: Path
):
    found = chunks(run_unblob(fixture, tmp_path, max_depth=1, pr1255="merged"))
    assert [(c.handler_name, c.start_offset, c.end_offset) for c in found] == [
        (handler, 0, fixture.stat().st_size)
    ]
