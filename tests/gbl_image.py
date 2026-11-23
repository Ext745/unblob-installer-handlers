"""GBL v3 fixtures for tests (FSD §13d), built with pygbl.

pygbl (zigpy/pygbl, Apache-2.0) is a test oracle only (§13d.1, §16.1): it
runs in tests/fixtures/build.sh, in the dev image's /opt/tools-venv, and the
files it writes are committed. The tests read those files and import only
the constants and the pygbl-free helpers below, so they also run where pygbl
is not installed (Python 3.10, TC-CON-02).

Usage: /opt/tools-venv/bin/python tests/gbl_image.py <payload> <outdir>
"""

import struct
import sys
import zlib
from pathlib import Path

HEADER_TAG = 0x03A617EB
END_TAG = 0xFC0404FC
PROG = 0xFE0101FE
LZ4 = 0xFD0505FD
LZMA = 0xFD0707FD
APP_INFO = 0xF40A0AF4
METADATA = 0xF60808F6
SIGNATURE = 0xF70A0AF7
TAG_HEADER = struct.Struct("<II")  # tag ID, length

# standard.gbl (FR-GBL-04): payload split into four program-data tags, two
# regions. (tag ID, address, payload slice)
STANDARD_LAYOUT = [
    (PROG, 0x00000000, slice(0, 1024)),
    (PROG, 0x00000400, slice(1024, 2048)),
    (LZ4, 0x00010000, slice(2048, 3072)),
    (LZMA, 0x00010400, slice(3072, 4096)),
]
STANDARD_REGIONS = {0x00000000: slice(0, 2048), 0x00010000: slice(2048, 4096)}

METADATA_BYTES = b"uih gbl fixture metadata"
SIGNATURE_BYTES = bytes(range(64))
PRODUCT_ID = bytes(range(16))
ENCRYPTION_KEY = bytes(range(16))  # throwaway, for the fixture only
NONCE = bytes(range(12))


def tag(tag_id: int, data: bytes) -> bytes:
    return TAG_HEADER.pack(tag_id, len(data)) + data


def with_end_tag(tags: bytes) -> bytes:
    """Append the end tag whose CRC-32 makes the whole stream's CRC 0x2144DF1C."""
    head = TAG_HEADER.pack(END_TAG, 4)
    return tags + head + struct.pack("<I", zlib.crc32(tags + head))


def recrc(gbl: bytes) -> bytes:
    """Recompute the end tag of an unpadded tag stream ending in one."""
    return with_end_tag(gbl[:-12])


def tags_of(gbl: bytes) -> list[tuple[int, int, int]]:
    """(tag ID, data offset, length) of every tag through the end tag."""
    out, pos = [], 0
    while True:
        tag_id, length = TAG_HEADER.unpack_from(gbl, pos)
        out.append((tag_id, pos + 8, length))
        pos += 8 + length
        if tag_id == END_TAG:
            return out


def main(payload_path: str, outdir: str) -> None:
    import pygbl.gbl3 as g  # noqa: PLC0415 - oracle, only where fixtures are built

    payload = Path(payload_path).read_bytes()
    assert len(payload) == 4096
    out = Path(outdir)
    # Version bytes 00 00 00 03 on the wire (FSD §13d.1, as Commander writes
    # them); pygbl reads the field big-endian, so that is version=3.
    header = g.GBL3Header(version=3, type=g.GBL3Type.NONE)
    make = {PROG: g.GBL3Prog, LZ4: g.GBL3ProgLZ4, LZMA: g.GBL3ProgLZMA}
    compress = {
        PROG: lambda d: d,
        LZ4: g.lz4_compress,
        LZMA: g.lzma_compress,
    }
    prog = [
        make[t](address=a, data=compress[t](payload[s])) for t, a, s in STANDARD_LAYOUT
    ]
    standard = g.GBL3Image(tags=[header, *prog]).regenerate_crc()
    (out / "standard.gbl").write_bytes(standard.serialize())

    signed = g.GBL3Header(version=3, type=g.GBL3Type.SIGNATURE_ECDSA_P256)
    tags = g.GBL3Image(
        tags=[
            signed,
            g.GBL3ApplicationInfo(
                type=g.GBL3ApplicationType.ZIGBEE,
                version=0x01020304,
                capabilities=0,
                product_id=PRODUCT_ID,
            ),
            g.GBL3Metadata(metadata=METADATA_BYTES),
            g.GBL3Signature(r=SIGNATURE_BYTES[:32], s=SIGNATURE_BYTES[32:]),
        ]
    ).regenerate_crc()
    (out / "tags.gbl").write_bytes(tags.serialize())

    encrypted = standard.encrypt(ENCRYPTION_KEY, nonce=NONCE)
    (out / "encrypted.gbl").write_bytes(encrypted.serialize())

    # Oracle: pygbl parses each back, and decompresses the standard file's
    # program data to the payload.
    for name in ("standard.gbl", "tags.gbl", "encrypted.gbl"):
        g.GBL3Image.from_bytes((out / name).read_bytes())
    back = g.GBL3Image.from_bytes((out / "standard.gbl").read_bytes())
    data = b"".join(
        t.data
        if isinstance(t, g.GBL3Prog)
        else g.lz4_decompress(t.data)
        if isinstance(t, g.GBL3ProgLZ4)
        else g.lzma_decompress(t.data)
        for t in back.tags
        if isinstance(t, (g.GBL3Prog, g.GBL3ProgLZ4, g.GBL3ProgLZMA))
    )
    assert data == payload
    sys.stdout.write(
        "gbl: pygbl parses all three; standard program data equals the payload\n"
    )


if __name__ == "__main__":
    main(*sys.argv[1:])
