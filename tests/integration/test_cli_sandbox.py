"""FR-COM-06 on the committed fixtures: the `unblob` command, sandbox on."""

import pytest

from tests.cli_sandbox import check_cli_matches_api
from tests.samples import COMMITTED


@pytest.mark.parametrize("name", COMMITTED)
def test_tc_com_06_cli_sandbox_matches_process_file(name: str, tmp_path):
    check_cli_matches_api(COMMITTED[name], tmp_path)
