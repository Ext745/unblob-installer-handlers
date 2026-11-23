"""Build Cypress/Infineon .cyacd and .cyacd2 files for tests (FSD §13e), from the FSD alone.

.cyacd (big-endian): a header line of 12 hex digits (silicon ID 4 bytes,
silicon revision 1, checksum type 1), then one line per flash row: ':',
array ID (1), row number (2), data length (2), data, checksum (1) = two's
complement of the low byte of the sum of the preceding row bytes.

.cyacd2 (little-endian, Infineon DFU SDK guide, Appendix C): a header line of
24 hex digits (file version 01, silicon ID 4, silicon revision 1, checksum
type 1, application ID 1, product ID 4), optional '@APPINFO:0x<addr>,0x<len>'
and '@EIV:<hex>' lines, then data lines ':' + address (4) + data.

Usage: python3 tests/cyacd_image.py <payload> <outdir>   (the committed fixtures)
"""

import sys
from pathlib import Path

SILICON_ID = 0x04C81193
SILICON_REV = 0x11
APP_ID = 0x01
PRODUCT_ID = 0x01020304
APPINFO = (0x10000000, 0x3000)
EIV = bytes(range(16))
ROW = 128

# standard.cyacd (FR-CYA-04): (array ID, row number) -> payload slice
CYACD_ROWS = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 5), (1, 0)]
# expected files: (array ID, byte offset, payload slice)
CYACD_FILES = [
    (0, 0x000, slice(0, 4 * ROW)),
    (0, 0x280, slice(4 * ROW, 5 * ROW)),
    (1, 0x000, slice(5 * ROW, 6 * ROW)),
]
# standard.cyacd2 (FR-CYA-05): (address, payload slice); the first two contiguous
CYACD2_LINES = [
    (0x10000000, slice(0, 256)),
    (0x10000100, slice(256, 512)),
    (0x10002000, slice(512, 768)),
]
CYACD2_FILES = [(0x10000000, slice(0, 512)), (0x10002000, slice(512, 768))]


def row_line(array_id: int, row: int, data: bytes) -> bytes:
    raw = (
        bytes([array_id]) + row.to_bytes(2, "big") + len(data).to_bytes(2, "big") + data
    )
    return b":" + (raw + bytes([-sum(raw) & 0xFF])).hex().upper().encode()


def cyacd(payload: bytes, rows=CYACD_ROWS, eol: bytes = b"\r\n") -> bytes:
    header = f"{SILICON_ID:08X}{SILICON_REV:02X}00".encode()
    lines = [header] + [
        row_line(a, r, payload[i * ROW : (i + 1) * ROW])
        for i, (a, r) in enumerate(rows)
    ]
    return eol.join(lines) + eol


def data_line(address: int, data: bytes) -> bytes:
    return b":" + (address.to_bytes(4, "little") + data).hex().upper().encode()


def cyacd2(payload: bytes, *, eiv: bool = False, eol: bytes = b"\n") -> bytes:
    header = (
        (
            bytes([1])
            + SILICON_ID.to_bytes(4, "little")
            + bytes([SILICON_REV, 0, APP_ID])
            + PRODUCT_ID.to_bytes(4, "little")
        )
        .hex()
        .upper()
        .encode()
    )
    lines = [header, f"@APPINFO:0x{APPINFO[0]:x},0x{APPINFO[1]:x}".encode()]
    if eiv:
        lines.append(b"@EIV:" + EIV.hex().encode())
    lines += [data_line(a, payload[s]) for a, s in CYACD2_LINES]
    return eol.join(lines) + eol


def main(payload_path: str, outdir: str) -> None:
    payload = Path(payload_path).read_bytes()
    out = Path(outdir)
    (out / "standard.cyacd").write_bytes(cyacd(payload))
    (out / "standard.cyacd2").write_bytes(cyacd2(payload))
    (out / "encrypted.cyacd2").write_bytes(cyacd2(payload, eiv=True))


if __name__ == "__main__":
    main(*sys.argv[1:])
