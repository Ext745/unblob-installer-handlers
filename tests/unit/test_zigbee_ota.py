"""Zigbee OTA chunk calculation (FSD §13c), Wave 3: malformed images declined."""

import importlib
from types import ModuleType

import pytest
from unblob.file_utils import InvalidInputFormat

from tests.read_recorder import ReadRecorder
from tests.zigbee_ota_image import BASE_HEADER, SUB_HEADER, build

UPGRADE = (0x0000, bytes(range(256)) * 4)
MANUFACTURER_TAG = (0xF000, b"manufacturer-data")


def zigbee_ota() -> ModuleType:
    # Imported per test, so the file is collected before the module exists.
    return importlib.import_module("unblob_installers.zigbee_ota")


def declined(data: bytes) -> ReadRecorder:
    """Run chunk calculation, expecting InvalidInputFormat and nothing else."""
    with ReadRecorder(data) as file, pytest.raises(InvalidInputFormat):
        zigbee_ota().ZigbeeOtaHandler().calculate_chunk(file, 0)
    return file


@pytest.mark.parametrize(
    "case",
    ["one byte past the input", "smaller than the header", "equal to the header"],
)
def test_tc_zota_02_bad_total_size_declined(case: str):
    good = build([UPGRADE])
    with ReadRecorder(good) as file:  # control: the same image, size intact
        chunk = zigbee_ota().ZigbeeOtaHandler().calculate_chunk(file, 0)
    assert chunk is not None
    assert (chunk.start_offset, chunk.end_offset) == (0, len(good))
    header = BASE_HEADER.size
    total = {
        "one byte past the input": len(good) + 1,
        "smaller than the header": header - 1,
        "equal to the header": header,
    }[case]
    file = declined(build([UPGRADE], total_size=total))
    assert not file.read_past_end, f"read to {file.highest} of {file.size()}"


@pytest.mark.parametrize("case", ["sub-element 1 byte too long", "5-byte remainder"])
def test_tc_zota_03_subelements_must_fill_the_image(case: str):
    if case == "sub-element 1 byte too long":
        # The last sub-element's length claims one byte the image does not hold.
        data = bytearray(build([UPGRADE, MANUFACTURER_TAG]))
        last = len(data) - len(MANUFACTURER_TAG[1]) - SUB_HEADER.size
        tag, length = SUB_HEADER.unpack_from(data, last)
        SUB_HEADER.pack_into(data, last, tag, length + 1)
        data = bytes(data)
    else:
        # Total image size 5 bytes past the last sub-element: shorter than a
        # 6-byte sub-element header. The bytes exist in the input.
        image = build([UPGRADE, MANUFACTURER_TAG])
        data = build([UPGRADE, MANUFACTURER_TAG], total_size=len(image) + 5)
        data += b"\0" * 5
    file = declined(data)
    assert not file.read_past_end, f"read to {file.highest} of {file.size()}"
