"""GBL against a real Gecko SDK build (FSD §13d, FR-GBL-07).

From the real-file store (D-4, MANIFEST.yaml): the Nabu Casa SkyConnect
Zigbee NCP 9.1.1.1 GBL (a version, scrub:allow) and the ELF it was built
from, one CI artifact. The oracle is the ELF's PT_LOAD file data at
p_paddr, read independently here (ELF32 little-endian program headers).
"""

import struct
from pathlib import Path

from tests.conftest import chunks, run_unblob

GBL = Path("gbl/skyconnect_zigbee_ncp_9.1.1.1.gbl")
ELF = Path("gbl/skyconnect_zigbee_ncp_9.1.1.1.out")
PT_LOAD = 1


def load_segments(elf: bytes) -> list[tuple[int, bytes]]:
    """(p_paddr, file data) of every PT_LOAD segment with file data."""
    assert elf[:6] == b"\x7fELF\x01\x01"  # ELF32, little-endian
    (phoff,) = struct.unpack_from("<I", elf, 0x1C)
    phentsize, phnum = struct.unpack_from("<HH", elf, 0x2A)
    segments = []
    for i in range(phnum):
        p_type, p_offset, _vaddr, p_paddr, p_filesz = struct.unpack_from(
            "<IIIII", elf, phoff + i * phentsize
        )
        if p_type == PT_LOAD and p_filesz:
            segments.append((p_paddr, elf[p_offset : p_offset + p_filesz]))
    return segments


def test_tc_gbl_07_real_gbl_regions_equal_the_elf(realfiles: Path, tmp_path: Path):
    segments = load_segments((realfiles / ELF).read_bytes())
    result = run_unblob(realfiles / GBL, tmp_path, max_depth=1)
    assert [c.handler_name for c in chunks(result)] == ["gbl"]
    regions = sorted(tmp_path.rglob("0x*.bin"))
    assert regions
    covered = 0
    for region in regions:
        start = int(region.stem, 16)
        data = region.read_bytes()
        pos = 0
        # Adjacent segments may share one region; every byte must come from one.
        while pos < len(data):
            address = start + pos
            match = [(a, seg) for a, seg in segments if a <= address < a + len(seg)]
            assert match, f"{region.name}: 0x{address:08x} is in no PT_LOAD segment"
            a, seg = match[0]
            take = min(len(seg) - (address - a), len(data) - pos)
            assert data[pos : pos + take] == seg[address - a : address - a + take]
            pos += take
        covered += len(data)
    assert covered > 0
