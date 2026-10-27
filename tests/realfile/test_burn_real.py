"""WiX/Burn against a real signed vendor bundle (FSD FR-BURN-04, FR-BURN-05, FR-PE-01)."""

from pathlib import Path

from tests.conftest import (
    BURN_NS,
    burn_container_file,
    burn_hash,
    burn_manifest,
    chunks,
    run_unblob,
)

VC_REDIST = Path("burn/vc_redist.x64.exe")


def test_tc_burn_06_signed_bundle_containers(realfiles: Path, tmp_path: Path):
    source = realfiles / VC_REDIST
    result = run_unblob(source, tmp_path, max_depth=2)
    top = [c for c in chunks(result) if c.handler_name == "wix_burn"]
    # FR-PE-01: the chunk runs through the certificate table, which ends the file.
    assert [(c.start_offset, c.end_offset) for c in top] == [(0, source.stat().st_size)]

    (out,) = [p for p in tmp_path.iterdir() if p.is_dir()]
    manifest = burn_manifest(out)
    # The attached container follows the original signature, not the UX container.
    for c in manifest.iter(f"{BURN_NS}Container"):
        data = (out / burn_container_file(manifest, c.get("Id"))).read_bytes()
        assert len(data) == int(c.attrib["FileSize"])
        assert burn_hash(data) == c.get("Hash")


def test_tc_burn_05_every_embedded_payload_extracted(realfiles: Path, tmp_path: Path):
    run_unblob(realfiles / VC_REDIST, tmp_path, max_depth=2)
    (out,) = [p for p in tmp_path.iterdir() if p.is_dir()]
    manifest = burn_manifest(out)

    payloads = [
        p
        for p in manifest.iter(f"{BURN_NS}Payload")
        if p.get("Packaging") == "embedded"
    ]
    assert payloads
    for p in payloads:
        container = burn_container_file(manifest, p.get("Container"))
        path = out / f"{container}_extract" / p.attrib["SourcePath"]
        data = path.read_bytes()
        assert len(data) == int(p.attrib["FileSize"]), p.get("FilePath")
        assert burn_hash(data) == p.get("Hash"), p.get("FilePath")
