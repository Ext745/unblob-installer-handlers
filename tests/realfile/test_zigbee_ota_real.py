"""Zigbee OTA against real vendor files (FSD §13c, FR-ZOTA-06).

Files from the real-file store (D-4, MANIFEST.yaml): three IKEA files (two
inside IKEA's signed wrapper) and one Philips Hue file. The oracle is the
OTA header and sub-element layout of FSD §13c.1, read independently here.
"""

import struct
from pathlib import Path

import pytest

from tests.conftest import chunks, run_unblob

# (path, OTA offset in the file, carries a GBL v3 upgrade image)
FILES = [
    ("zigbee-ota/10082264-zingo_lds_stoftmoln-1.1.7.ota.ota.signed", 616, True),
    (
        "zigbee-ota/inspelning-smart-plug-soc_release_prod_v33816645_02579ff4-6fec-42f6-8957-4048def87def.ota",
        0,
        True,
    ),
    ("zigbee-ota/10035515-TRADFRI-bulb-cws-2.3.093.ota.ota.signed", 488, False),
    ("zigbee-ota/100B-010C-01001A02-ConfLight-Lamps_0012.zigbee", 0, False),
]


def upgrade_image(data: bytes, offset: int) -> tuple[int, bytes]:
    """(total image size, tag 0x0000 data) read from the FSD §13c.1 layout."""
    header_length = struct.unpack_from("<H", data, offset + 6)[0]
    total = struct.unpack_from("<I", data, offset + 52)[0]
    pos = offset + header_length
    while pos < offset + total:
        tag, length = struct.unpack_from("<HI", data, pos)
        if tag == 0x0000:
            return total, data[pos + 6 : pos + 6 + length]
        pos += 6 + length
    raise AssertionError("no upgrade image")


@pytest.mark.parametrize("name,offset,has_gbl", FILES, ids=[f[0] for f in FILES])
def test_tc_zota_06_real_ota_files_give_their_upgrade_image(
    name: str, offset: int, has_gbl: bool, realfiles: Path, tmp_path: Path
):
    path = realfiles / name
    data = path.read_bytes()
    total, image = upgrade_image(data, offset)
    result = run_unblob(path, tmp_path)
    found = [
        (c.start_offset, c.end_offset)
        for c in chunks(result)
        if c.handler_name == "zigbee_ota"
    ]
    assert (offset, offset + total) in found
    written = next(tmp_path.rglob("tag_0x0000_*.bin")).read_bytes()
    assert written == image
    if has_gbl:
        assert any(c.handler_name == "gbl" for c in chunks(result))
