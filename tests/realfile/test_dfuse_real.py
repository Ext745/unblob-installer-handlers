"""DfuSe against a real vendor file: Flipper Zero 1.5.1 (FSD FR-DFU-01, FR-DFU-06)."""

from pathlib import Path

from tests.conftest import chunks, run_unblob

DFU = Path("dfuse/flipper-z-f7-full-1.5.1.dfu")
BIN = Path("dfuse/flipper-z-f7-full-1.5.1.bin")


def test_tc_dfu_01_flipper_whole_file_is_one_chunk(realfiles: Path, tmp_path: Path):
    dfu = realfiles / DFU
    found = [c for c in chunks(run_unblob(dfu, tmp_path)) if c.handler_name == "dfuse"]
    assert [(c.start_offset, c.end_offset) for c in found] == [(0, dfu.stat().st_size)]


def test_tc_dfu_06_flipper_element_equals_vendor_bin(realfiles: Path, tmp_path: Path):
    run_unblob(realfiles / DFU, tmp_path)
    elements = sorted(
        p for p in tmp_path.rglob("0x*.bin") if p.parent.name.startswith("target")
    )
    assert [f"{p.parent.name}/{p.name}" for p in elements] == [
        "target0_Flipper_Zero_F7/0x08000000.bin"
    ]
    assert elements[0].read_bytes() == (realfiles / BIN).read_bytes()
