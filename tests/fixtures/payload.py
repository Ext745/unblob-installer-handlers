"""The fixture payload: 4 KiB that cannot occur by chance.

A 16-byte tag followed by SHA-256 counter-mode bytes from a fixed seed, so a
match in any extracted output is unambiguous (testing standard: test data).
"""

import hashlib
import sys

TAG = b"UIH-FIXTURE-v1\x00\x00"
SIZE = 4096


def payload() -> bytes:
    out = bytearray(TAG)
    n = 0
    while len(out) < SIZE:
        out += hashlib.sha256(
            b"unblob-installer-handlers" + n.to_bytes(4, "little")
        ).digest()
        n += 1
    return bytes(out[:SIZE])


if __name__ == "__main__":
    sys.stdout.buffer.write(payload())
