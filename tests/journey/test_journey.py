"""The standard run (testing/test-plan.yaml JRN-*), one test per step.

JRN-01: a board UF2 through the plugin. JRN-02: a vendor Inno Setup updater
(FSD Phase 3; needs PR #1255's PE handler and the Inno handler).
"""

from pathlib import Path

import pytest
from unblob.plugins import UnblobPluginManager

from tests.conftest import chunks, run_unblob

pytestmark = pytest.mark.journey

PICO = Path("boards/rp2040-pico-sdk")
NAVX = Path("inno/navx-mxp-setup.exe")


@pytest.mark.xfail(reason="FR-PKG-01: uf2 handler absent", strict=True)
def test_jrn_01_1_plugin_registers_its_handlers():
    pm = UnblobPluginManager()
    pm.load_setuptools_entrypoints()
    names = {h.NAME for group in pm.hook.unblob_register_handlers() for h in group}
    assert "uf2" in names


@pytest.mark.xfail(reason="FR-UF2-01/02: uf2 handler absent", strict=True)
def test_jrn_01_2_board_uf2_is_one_uf2_chunk(realfiles: Path, tmp_path: Path):
    uf2 = realfiles / PICO / "uih_rp2040_hello.uf2"
    found = chunks(run_unblob(uf2, tmp_path))
    assert [(c.handler_name, c.start_offset, c.end_offset) for c in found] == [
        ("uf2", 0, uf2.stat().st_size)
    ]


@pytest.mark.xfail(reason="FR-UF2-04/05/09: uf2 handler absent", strict=True)
def test_jrn_01_3_region_equals_build_bin(realfiles: Path, tmp_path: Path):
    run_unblob(realfiles / PICO / "uih_rp2040_hello.uf2", tmp_path)
    region = next(tmp_path.rglob("RP2040/0x10000000.bin"))
    assert (
        region.read_bytes() == (realfiles / PICO / "uih_rp2040_hello.bin").read_bytes()
    )


@pytest.mark.xfail(
    reason="FR-INNO-01, FR-PE-01: FSD Phase 3 (inno handler, PR #1255)", run=False
)
def test_jrn_02_1_vendor_updater_is_one_inno_chunk(realfiles: Path, tmp_path: Path):
    exe = realfiles / NAVX
    found = [c for c in chunks(run_unblob(exe, tmp_path)) if c.handler_name == "inno"]
    assert [(c.start_offset, c.end_offset) for c in found] == [(0, exe.stat().st_size)]


@pytest.mark.xfail(reason="FR-INNO-03: FSD Phase 3 (inno handler)", run=False)
def test_jrn_02_2_installer_files_extracted(realfiles: Path, tmp_path: Path):
    run_unblob(realfiles / NAVX, tmp_path)
    assert list(tmp_path.rglob("navx2-mxp_4.0.447.hex"))


@pytest.mark.xfail(
    reason="FR-INNO-04: FSD Phase 3 (inno handler; Intel HEX handler for recursion)",
    run=False,
)
def test_jrn_02_3_firmware_payload_unpacked_further(realfiles: Path, tmp_path: Path):
    run_unblob(realfiles / NAVX, tmp_path)
    hexfile = next(tmp_path.rglob("navx2-mxp_4.0.447.hex"))
    assert list(hexfile.parent.rglob("navx2-mxp_4.0.447.hex_extract/*.bin"))
