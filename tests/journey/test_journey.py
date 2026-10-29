"""The standard run (testing/test-plan.yaml JRN-*), one test per step.

JRN-01: a board UF2 through the plugin. JRN-02: a vendor Inno Setup updater
(FSD Phase 3; needs PR #1255's PE handler and the Inno handler).
"""

import shutil
import subprocess
from pathlib import Path

import pytest
from unblob.plugins import UnblobPluginManager
from unblob.report import ChunkReport

from tests.conftest import chunks, run_unblob, tree
from tests.uf2image import payload_image

pytestmark = pytest.mark.journey

PICO = Path("boards/rp2040-pico-sdk")
NAVX = Path("inno/navx-mxp-setup.exe")


# FSD §5: every handler this package ships, by name, not read from the package.
HANDLER_NAMES = {
    "uf2",
    "ihex",
    "dfuse",
    "mcuboot",
    "installshield",
    "inno",
    "setup_factory",
    "wix_burn",
}
DIR_HANDLER_NAMES = {"installshield_set"}


def test_jrn_01_1_plugin_registers_its_handlers():
    pm = UnblobPluginManager()
    pm.load_setuptools_entrypoints()
    names = {h.NAME for group in pm.hook.unblob_register_handlers() for h in group}
    dir_names = {
        h.NAME for group in pm.hook.unblob_register_dir_handlers() for h in group
    }
    # Every handler, not just one: none of them may need -P (FR-PKG-01).
    assert names >= HANDLER_NAMES, HANDLER_NAMES - names
    assert dir_names >= DIR_HANDLER_NAMES, DIR_HANDLER_NAMES - dir_names


def test_jrn_01_2_board_uf2_is_one_uf2_chunk(realfiles: Path, tmp_path: Path):
    uf2 = realfiles / PICO / "uih_rp2040_hello.uf2"
    found = chunks(run_unblob(uf2, tmp_path))
    assert [(c.handler_name, c.start_offset, c.end_offset) for c in found] == [
        ("uf2", 0, uf2.stat().st_size)
    ]


def test_jrn_01_3_region_equals_build_bin(realfiles: Path, tmp_path: Path):
    uf2 = realfiles / PICO / "uih_rp2040_hello.uf2"
    run_unblob(uf2, tmp_path)
    region = next(tmp_path.rglob("RP2040/0x10000000.bin")).read_bytes()
    build = (realfiles / PICO / "uih_rp2040_hello.bin").read_bytes()
    # FR-UF2-09: what the UF2 writes, equal to the build over its length.
    assert region == payload_image(uf2)[1]
    assert region[: len(build)] == build


def test_jrn_02_1_vendor_updater_is_one_inno_chunk(realfiles: Path, tmp_path: Path):
    exe = realfiles / NAVX
    result = run_unblob(exe, tmp_path, max_depth=1, pr1255="plugin")
    # At the updater's own level: our inno chunk alone, no pe chunk from #1255.
    found = [
        c
        for t in result.results
        if t.task.path == exe
        for c in t.reports
        if isinstance(c, ChunkReport)
    ]
    assert [(c.handler_name, c.start_offset, c.end_offset) for c in found] == [
        ("inno", 0, exe.stat().st_size)
    ]


def test_jrn_02_2_installer_files_extracted(realfiles: Path, tmp_path: Path):
    innoextract = shutil.which("innoextract")
    if innoextract is None:
        pytest.skip("precondition unmet: innoextract (extractors) not installed")
    oracle = tmp_path / "oracle"
    subprocess.run(
        [innoextract, "-e", "-s", "-d", str(oracle), str(realfiles / NAVX)],
        check=True,
    )
    run_unblob(realfiles / NAVX, tmp_path / "x", max_depth=1)
    (out,) = [p for p in (tmp_path / "x").iterdir() if p.is_dir()]

    # Same file set and SHA-256 per file as innoextract -e, payload included.
    found = tree(out)
    assert found == tree(oracle)
    assert any(name.endswith("/navx2-mxp_4.0.447.hex") for name in found)


def test_jrn_02_3_firmware_payload_unpacked_further(realfiles: Path, tmp_path: Path):
    # Depth 2: the installer, then the .hex inside it (deeper costs ~20 minutes).
    run_unblob(realfiles / NAVX, tmp_path, max_depth=2)
    hexfile = next(tmp_path.rglob("navx2-mxp_4.0.447.hex"))
    assert list(hexfile.parent.rglob("navx2-mxp_4.0.447.hex_extract/*.bin"))
