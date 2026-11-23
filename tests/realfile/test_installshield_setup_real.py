"""A real headered InstallShield single-file installer (FSD §13a, FR-ISW-06).

From the real-file store (D-4, MANIFEST.yaml): the UPS Thermal Printing
setup.exe, an `ISSetupStream` package carrying an MSI. Run with unblob's own
handlers too, so the MSI is extracted further by recursion.
"""

import hashlib
from pathlib import Path

from unblob.handlers import BUILTIN_HANDLERS
from unblob.processing import ExtractionConfig, process_file
from unblob.report import ChunkReport

from unblob_installers import HANDLERS

UPS = Path("installshield-setup/ups-thermal-printing-setup.exe")
UPS_SHA256 = "6906713e51b315cbebb374b9d0bd20131abbd3e52ffbea0fc92e63f61e14ba50"
UPS_PACKAGE = (1233920, 12200809)  # PE image end .. last member's data end
OLE_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")


def test_tc_isw_06_real_package_members_and_msi_recursion(
    realfiles: Path, tmp_path: Path
):
    source = realfiles / UPS
    assert hashlib.sha256(source.read_bytes()).hexdigest() == UPS_SHA256
    config = ExtractionConfig(
        extract_root=tmp_path,
        randomness_depth=0,
        keep_extracted_chunks=True,
        handlers=(*HANDLERS, *BUILTIN_HANDLERS),
        max_depth=3,
    )
    result = process_file(config, source)
    reports = [
        r for t in result.results for r in t.reports if isinstance(r, ChunkReport)
    ]
    assert (
        "installshield_setup",
        *UPS_PACKAGE,
    ) in [(c.handler_name, c.start_offset, c.end_offset) for c in reports]
    members = next(tmp_path.rglob("*.installshield_setup_extract"))
    assert (members / "Setup.ini").is_file()
    msi = members / "UPS Thermal Printing.msi"
    assert msi.read_bytes()[:8] == OLE_MAGIC  # de-obfuscated and inflated
    # unblob's recursion takes the MSI further
    assert any(p.is_file() for p in members.rglob("UPS Thermal Printing.msi_extract/*"))
