"""PKWARE DCL implode decompression, for Setup Factory scripts (FSD §8).

Ported from sfextract's blast.py (Copyright (c) 2020 Crown Copyright,
Government of Canada (Canadian Centre for Cyber Security / Communications
Security Establishment), MIT License), itself a conversion of Mark Adler's
zlib contrib/blast/blast.c. Restated to read from a byte buffer and to raise
ValueError on truncated or malformed input.

MIT License: Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including without
limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom
the Software is furnished to do so, subject to the following conditions: The
above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS
IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE
AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

MAXBITS = 13  # longest code
END_OF_STREAM = 519  # the length that ends the data

# Code lengths, run-length encoded as in blast.c: (count - 1) << 4 | length.
# fmt: off
LIT_LENGTHS = [
    11, 124, 8, 7, 28, 7, 188, 13, 76, 4, 10, 8, 12, 10, 12, 10, 8, 23, 8,
    9, 7, 6, 7, 8, 7, 6, 55, 8, 23, 24, 12, 11, 7, 9, 11, 12, 6, 7, 22, 5,
    7, 24, 6, 11, 9, 6, 7, 22, 7, 11, 38, 7, 9, 8, 25, 11, 8, 11, 9, 12,
    8, 12, 5, 38, 5, 38, 5, 11, 7, 5, 6, 21, 6, 10, 53, 8, 7, 24, 10, 27,
    44, 253, 253, 253, 252, 252, 252, 13, 12, 45, 12, 45, 12, 61, 12, 45,
    44, 173,
]
# fmt: on
LEN_LENGTHS = [2, 35, 36, 53, 38, 23]
DIST_LENGTHS = [2, 20, 53, 230, 247, 151, 248]
LENGTH_BASE = [3, 2, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 40, 72, 136, 264]
LENGTH_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8]


class _Huffman:
    """Canonical code: counts per length (1..MAXBITS) and symbols in code order."""

    def __init__(self, rep: list[int]):
        lengths = []
        for byte in rep:
            lengths += [byte & 0x0F] * ((byte >> 4) + 1)
        self.count = [0] * (MAXBITS + 1)
        for length in lengths:
            self.count[length] += 1
        offsets = [0] * (MAXBITS + 1)
        for length in range(1, MAXBITS):
            offsets[length + 1] = offsets[length] + self.count[length]
        self.symbol = [0] * len(lengths)
        for symbol, length in enumerate(lengths):
            if length:
                self.symbol[offsets[length]] = symbol
                offsets[length] += 1


LIT = _Huffman(LIT_LENGTHS)
LEN = _Huffman(LEN_LENGTHS)
DIST = _Huffman(DIST_LENGTHS)


class _Bits:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0  # bit position

    def bits(self, n: int) -> int:
        value = 0
        for i in range(n):
            byte = self.pos >> 3
            if byte >= len(self.data):
                raise ValueError("PKWARE data truncated")
            value |= ((self.data[byte] >> (self.pos & 7)) & 1) << i
            self.pos += 1
        return value

    def decode(self, h: _Huffman) -> int:
        code = first = index = 0
        for length in range(1, MAXBITS + 1):
            code |= self.bits(1) ^ 1  # codes are stored bit-inverted
            count = h.count[length]
            if code < first + count:
                return h.symbol[index + code - first]
            index += count
            first = (first + count) << 1
            code <<= 1
        raise ValueError("invalid PKWARE code")


def _copy_match(s: _Bits, out: bytearray, dict_bits: int) -> bool:
    """Append one length/distance match; False at the end of the stream."""
    sym = s.decode(LEN)
    length = LENGTH_BASE[sym] + s.bits(LENGTH_EXTRA[sym])
    if length == END_OF_STREAM:
        return False
    shift = 2 if length == 2 else dict_bits
    distance = (s.decode(DIST) << shift) + s.bits(shift) + 1
    if distance > len(out):
        raise ValueError("PKWARE distance before the start of the data")
    for _ in range(length):
        out.append(out[-distance])
    return True


def decompress(data: bytes, limit: int) -> bytearray:
    """Decompress PKWARE DCL implode data, at most limit bytes of output."""
    if len(data) < 2:
        raise ValueError("PKWARE header truncated")
    coded, dict_bits = data[0], data[1]
    if coded > 1 or not 4 <= dict_bits <= 6:
        raise ValueError("invalid PKWARE header")
    s = _Bits(data[2:])
    out = bytearray()
    while len(out) <= limit:
        if not s.bits(1):
            out.append(s.decode(LIT) if coded else s.bits(8))
        elif not _copy_match(s, out, dict_bits):
            return out  # not copied: a script near the limit is held once
    raise ValueError("PKWARE output over the limit")
