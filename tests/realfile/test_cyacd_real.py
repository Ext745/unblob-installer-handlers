"""Real .cyacd and .cyacd2 files against the Intel HEX of the same build (FSD §13e, FR-CYA-07).

From the real-file store (D-4, MANIFEST.yaml): Arachnid Labs Reload Pro v1.0
(PSoC 4 .cyacd + .hex) and Infineon's WLC1 example (.cyacd2 + .hex). The
oracle is the .hex, read here independently (data, extended segment and
extended linear address records).
"""

import binascii
from pathlib import Path

from tests.conftest import chunks, run_unblob

CYACD = Path("cyacd/Reload Pro v1.0.cyacd")
CYACD_HEX = Path("cyacd/Reload Pro v1.0.hex")
CYACD2 = Path("cyacd/mtb-example-wicg1_ptx_epp_1_0_0_168_0_0_0_wi_custom.cyacd2")
CYACD2_HEX = Path("cyacd/mtb-example-wicg1_ptx_epp_1_0_0_168_0_0_0_wi_custom.hex")


def hex_bytes(text: bytes) -> dict[int, int]:
    """Address -> byte of every data record of an Intel HEX file."""
    memory: dict[int, int] = {}
    base = 0
    for line in text.splitlines():
        if not line.startswith(b":"):
            continue
        raw = binascii.unhexlify(line[1:])
        count, address, rtype, data = (
            raw[0],
            int.from_bytes(raw[1:3], "big"),
            raw[3],
            raw[4:-1],
        )
        assert len(data) == count
        if rtype == 0:
            for i, b in enumerate(data):
                memory[base + address + i] = b
        elif rtype == 1:
            break
        elif rtype == 2:
            base = int.from_bytes(data, "big") << 4
        elif rtype == 4:
            base = int.from_bytes(data, "big") << 16
    return memory


def test_tc_cya_07_real_cyacd_equals_its_hex(realfiles: Path, tmp_path: Path):
    memory = hex_bytes((realfiles / CYACD_HEX).read_bytes())
    result = run_unblob(realfiles / CYACD, tmp_path, max_depth=1)
    assert [c.handler_name for c in chunks(result)] == ["cyacd"]
    files = sorted(tmp_path.rglob("array_0x00/0x*.bin"))
    assert files
    assert not list(tmp_path.rglob("array_0x0[1-9a-f]"))  # PSoC 4: one array
    for f in files:
        offset = int(f.stem, 16)  # PSoC 4: address = byte offset
        data = f.read_bytes()
        assert bytes(memory[offset + i] for i in range(len(data))) == data, f.name


def test_tc_cya_07_real_cyacd2_equals_its_hex(realfiles: Path, tmp_path: Path):
    memory = hex_bytes((realfiles / CYACD2_HEX).read_bytes())
    result = run_unblob(realfiles / CYACD2, tmp_path, max_depth=1)
    assert [c.handler_name for c in chunks(result)] == ["cyacd2"]
    files = sorted(tmp_path.rglob("0x*.bin"))
    assert files
    compared = 0
    for f in files:
        start = int(f.stem, 16)
        for i, b in enumerate(f.read_bytes()):
            if start + i in memory:  # equal wherever both cover
                assert memory[start + i] == b, f"{f.name} +0x{i:x}"
                compared += 1
    # Most of the image is in both (the .cyacd2 adds zero rows 0x1f100..0x1fbff).
    assert compared > 100_000
