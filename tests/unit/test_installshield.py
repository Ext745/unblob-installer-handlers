"""InstallShield cabinet layout checks (FSD §6) on hand-built headers."""

import struct

import pytest
from unblob.file_utils import File, InvalidInputFormat

from tests.samples import handler

V21 = 0x04000834  # InstallShield 2015+ (the Realtek set's version)


@pytest.mark.parametrize("descriptor_size", [0, 29456], ids=["data-cab", "hdr"])
def test_tc_isc_06_v6_cabinet_file_not_claimed(descriptor_size: int):
    header = struct.pack("<4sIIII", b"ISc(", V21, 0, 0x200, descriptor_size)
    data = header + bytes(0x200 + descriptor_size)
    with (
        File.from_bytes(data) as file,
        pytest.raises(InvalidInputFormat, match="version 5"),
    ):
        handler("installshield").calculate_chunk(file, 0)
