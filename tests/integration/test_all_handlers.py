"""unblob's own integration test, on this package's fixtures (FSD C-09).

Each tests/integration/**/__input__ is extracted the way unblob's
test_all_handlers does it, with this package's handlers loaded, and the
result must equal the committed __output__ beside it. Regenerate with
`python -m tests.integration.build_outputs`.
"""

import pytest
from unblob.testing import (
    check_output_is_the_same,
    check_result,
    gather_integration_tests,
)

from tests.conftest import INTEGRATION, run_unblob


@pytest.mark.parametrize(
    "input_dir,output_dir", list(gather_integration_tests(INTEGRATION))
)
def test_tc_con_14_extraction_matches_committed_output(input_dir, output_dir, tmp_path):
    for input_file in sorted(input_dir.iterdir()):
        check_result(run_unblob(input_file, tmp_path))
    check_output_is_the_same(output_dir, tmp_path)
