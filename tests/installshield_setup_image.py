r"""Build headered InstallShield single-file packages for tests (FSD §13a), from §13a.1 alone.

All fields little-endian. Header, 46 bytes: signature (14) at 0x00
(`InstallShield\\0` classic, `ISSetupStream\\0` stream), file count (u16) at
0x0E, layout type (u32) at 0x10, 26 further bytes. Each member record is
directly followed by its data.

Classic record, 0x138 bytes: name (260, NUL-padded) at 0x000, flags (u32) at
0x104, data length (u32) at 0x10C, deflated marker (u16) at 0x118. Seed = the
name's bytes. Stream record, 0x18 bytes: name length in bytes (u32) at 0x00,
flags (u32) at 0x04, data length (u32) at 0x0A, deflated marker (u16) at 0x16;
for layout type 4 a further 0x18 bytes; then the UTF-16LE name. Seed = the
name in UTF-8.

Obfuscation: key[i] = NOT(seed[i] XOR (13 35 86 07)[i mod 4]); stored byte c
at position p decodes to nibble-swap(c) XOR key[(p mod B) mod len(key)], with
B = 1024 for flag 0x4, B = the data length for flag 0x2 alone on the classic
layout, and no obfuscation otherwise. A deflated member is a zlib stream
after decoding.

Usage: python3 tests/installshield_setup_image.py <payload> <outdir>
"""

import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

CLASSIC = b"InstallShield\x00"
STREAM = b"ISSetupStream\x00"
KEY_MAGIC = (0x13, 0x35, 0x86, 0x07)
M1024, MFILE = 0x4, 0x2


@dataclass(frozen=True)
class Member:
    name: str
    content: bytes
    flags: int = 0
    deflated: bool = False


def _nibble_swap(b: int) -> int:
    return ((b << 4) | (b >> 4)) & 0xFF


def obfuscate(data: bytes, seed: bytes, block: int | None) -> bytes:
    """Inverse of the §13a.1 decoding."""
    if block is None:
        return data
    key = bytes(~(s ^ KEY_MAGIC[i % 4]) & 0xFF for i, s in enumerate(seed))
    return bytes(
        _nibble_swap(d ^ key[(p % block) % len(key)]) for p, d in enumerate(data)
    )


def _stored(member: Member, seed: bytes, *, stream: bool) -> bytes:
    data = zlib.compress(member.content) if member.deflated else member.content
    if member.flags & M1024:
        block = 1024
    elif member.flags & MFILE and not stream:
        block = len(data)
    else:
        block = None
    return obfuscate(data, seed, block)


def header(signature: bytes, count: int, layout: int) -> bytes:
    return signature + struct.pack("<HI", count, layout) + bytes(26)


def classic(members: list[Member], layout: int = 0) -> bytes:
    out = [header(CLASSIC, len(members), layout)]
    for m in members:
        raw_name = m.name.encode("latin-1")
        data = _stored(m, raw_name, stream=False)
        record = bytearray(0x138)
        record[: len(raw_name)] = raw_name
        struct.pack_into("<I", record, 0x104, m.flags)
        struct.pack_into("<I", record, 0x10C, len(data))
        struct.pack_into("<H", record, 0x118, 1 if m.deflated else 0)
        out += [bytes(record), data]
    return b"".join(out)


def stream(members: list[Member], layout: int = 3) -> bytes:
    out = [header(STREAM, len(members), layout)]
    for m in members:
        name = m.name.encode("utf-16-le")
        data = _stored(m, m.name.encode("utf-8"), stream=True)
        record = bytearray(0x18)
        struct.pack_into("<I", record, 0x00, len(name))
        struct.pack_into("<I", record, 0x04, m.flags)
        struct.pack_into("<I", record, 0x0A, len(data))
        struct.pack_into("<H", record, 0x16, 1 if m.deflated else 0)
        extra = bytes(0x18) if layout == 4 else b""
        out += [bytes(record), extra, name, data]
    return b"".join(out)


def classic_members(payload: bytes) -> list[Member]:
    return [
        Member("plain.txt", b"stored as is\r\n"),
        Member("m1024.bin", payload, M1024),  # 4 KiB: the key restarts 4 times
        Member("mfile.bin", payload[:1500], MFILE),
        Member("lang\\0x0409.ini", b"[0x0409]\r\nTITLE=Fixture\r\n" * 40, M1024, True),
    ]


def stream_members(payload: bytes) -> list[Member]:
    return [
        Member("setup.msi", payload * 2, M1024, True),
        Member("flag2-plain.bin", payload[:700], MFILE),  # stored plain on stream
        Member("unicode é.ini", "[Info]\r\nName=été\r\n".encode("utf-16"), M1024),
    ]


def main(payload_path: str, outdir: str) -> None:
    payload = Path(payload_path).read_bytes()
    out = Path(outdir)
    (out / "classic.pftw").write_bytes(classic(classic_members(payload)))
    (out / "stream.pftw").write_bytes(stream(stream_members(payload)))
    (out / "stream4.pftw").write_bytes(stream(stream_members(payload), layout=4))


if __name__ == "__main__":
    main(*sys.argv[1:])
