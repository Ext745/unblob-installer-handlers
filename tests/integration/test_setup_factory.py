"""Setup Factory handler run by unblob on committed fixtures (FSD §8, §17).

Setup Factory itself has no committed fixture (tests/fixtures/SOURCES.md);
these are the files the handler must not claim.
"""

from pathlib import Path

import pytest

from tests.conftest import INPUTS, chunks, run_unblob
from tests.samples import PLAIN_PE


@pytest.mark.parametrize(
    "sample",
    [PLAIN_PE, INPUTS["inno"] / "standard-5.6.1-unicode.exe"],
    ids=["plain-pe", "inno"],
)
def test_tc_sf_02_pe_without_setup_factory_data_not_claimed(
    sample: Path, tmp_path: Path
):
    if not sample.is_file():
        pytest.skip(f"precondition unmet: {sample} not installed")
    found = chunks(run_unblob(sample, tmp_path, max_depth=1))
    assert "setup_factory" not in [c.handler_name for c in found]
