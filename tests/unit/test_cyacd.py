"""Cypress .cyacd and Infineon .cyacd2 chunk recognition (FSD §13e), unit tier."""

import pytest
from unblob.file_utils import InvalidInputFormat
from unblob.models import File

from tests.conftest import INPUTS
from unblob_installers.cyacd import Cyacd2Handler, CyacdHandler

PREAMBLE = b"unrelated line one\nsecond line\nthird line\n"


def fixture(handler: str, name: str) -> bytes:
    return (INPUTS[handler] / name).read_bytes()


def test_tc_cya_01_unit_cyacd_header_line():
    cyacd = fixture("cyacd", "standard.cyacd")
    chunk = CyacdHandler().calculate_chunk(
        File.from_bytes(PREAMBLE + cyacd), len(PREAMBLE)
    )
    assert chunk is not None
    assert (chunk.start_offset, chunk.end_offset) == (
        len(PREAMBLE),
        len(PREAMBLE) + len(cyacd),
    )


@pytest.mark.parametrize(
    "data,start",
    [
        (b"0123456789AB\n:this is not a row\n", 0),
        (b"FF0123456789AB\n:00000000800\n", 2),  # inside a longer hex run
    ],
)
def test_tc_cya_01_unit_not_a_cyacd(data: bytes, start: int):
    with pytest.raises(InvalidInputFormat):
        CyacdHandler().calculate_chunk(File.from_bytes(data), start)


def test_tc_cya_10_unit_cyacd2_header_line():
    cyacd2 = fixture("cyacd2", "standard.cyacd2")
    data = PREAMBLE + cyacd2
    chunk = Cyacd2Handler().calculate_chunk(File.from_bytes(data), len(PREAMBLE))
    assert chunk is not None
    assert (chunk.start_offset, chunk.end_offset) == (len(PREAMBLE), len(data))


@pytest.mark.parametrize("variant", ["version 02", "cyacd file"])
def test_tc_cya_10_unit_not_a_cyacd2(variant: str):
    if variant == "version 02":
        data = b"02" + fixture("cyacd2", "standard.cyacd2")[2:]
    else:
        data = fixture("cyacd", "standard.cyacd")
    with pytest.raises(InvalidInputFormat):
        Cyacd2Handler().calculate_chunk(File.from_bytes(data), 0)
