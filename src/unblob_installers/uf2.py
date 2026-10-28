"""UF2 handler (FSD §10).

Format: https://github.com/microsoft/uf2 (512-byte blocks, three magics).
"""

import json
import struct
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from pathlib import Path, PurePosixPath

from unblob.file_utils import InvalidInputFormat
from unblob.models import (
    Extractor,
    ExtractResult,
    File,
    Handler,
    HandlerDoc,
    HandlerType,
    HexString,
    Reference,
    ValidChunk,
)
from unblob.report import ExtractionProblem

from ._extract import require_whole_chunk
from ._regions import OverlapConflictError, assemble, region_name

BLOCK_SIZE = 512
MAX_PAYLOAD = 476
MAGIC_START0 = 0x0A324655
MAGIC_START1 = 0x9E5D5157
MAGIC_END = 0x0AB16F30
FLAG_NOT_MAIN_FLASH = 0x00000001
FLAG_FAMILY_ID = 0x00002000
NO_FAMILY = "no_family"

_HEADER = struct.Struct("<8I")


@dataclass(frozen=True)
class Block:
    flags: int
    target_addr: int
    payload: bytes
    block_no: int
    family_id: int | None


def parse_block(raw: bytes) -> Block | None:
    """Return the block in a 512-byte buffer, or None if it is not a valid UF2 block."""
    if len(raw) < BLOCK_SIZE:
        return None
    start0, start1, flags, addr, size, block_no, _total, family = _HEADER.unpack_from(
        raw
    )
    (end,) = struct.unpack_from("<I", raw, BLOCK_SIZE - 4)
    if (start0, start1, end) != (MAGIC_START0, MAGIC_START1, MAGIC_END):
        return None
    if size > MAX_PAYLOAD:
        return None
    return Block(
        flags=flags,
        target_addr=addr,
        payload=bytes(raw[32 : 32 + size]),
        block_no=block_no,
        family_id=family if flags & FLAG_FAMILY_ID else None,
    )


@cache
def _family_names() -> dict[int, str]:
    # uf2families.json from microsoft/uf2 at 90e9741 (FSD D-3).
    data = files("unblob_installers").joinpath("data/uf2families.json")
    table = json.loads(data.read_text())
    return {int(entry["id"], 16): entry["short_name"] for entry in table}


def family_dir(family_id: int | None) -> str:
    if family_id is None:
        return NO_FAMILY
    return _family_names().get(family_id, f"0x{family_id:08x}")


def region_path(family_id: int | None, address: int) -> PurePosixPath:
    """`<family>/0x<address>.bin` (FR-UF2-05, FR-UF2-06)."""
    return PurePosixPath(family_dir(family_id)) / region_name(address)


def blocks(data: bytes) -> list[Block]:
    """Return the run of valid blocks at the start of data."""
    found = []
    for offset in range(0, len(data) - BLOCK_SIZE + 1, BLOCK_SIZE):
        block = parse_block(data[offset : offset + BLOCK_SIZE])
        if block is None:
            break
        found.append(block)
    return found


class UF2Extractor(Extractor):
    def extract(self, inpath: Path, outdir: Path) -> ExtractResult | None:
        require_whole_chunk(UF2Handler().calculate_chunk, inpath)
        by_family: dict[int | None, list[tuple[int, bytes, int]]] = {}
        for block in blocks(inpath.read_bytes()):
            if block.flags & FLAG_NOT_MAIN_FLASH:
                continue
            by_family.setdefault(block.family_id, []).append(
                (block.target_addr, block.payload, block.block_no)
            )
        problems = []
        for family_id, writes in by_family.items():
            try:
                regions = assemble(writes)
            except OverlapConflictError as exc:
                problems.append(
                    ExtractionProblem(
                        path=str(inpath),
                        problem=f"UF2 blocks {exc.first} and {exc.second} write different bytes at 0x{exc.address:08x}",
                        resolution="family not extracted",
                    )
                )
                continue
            for address, data in regions:
                target = outdir / region_path(family_id, address)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        return ExtractResult(reports=problems)


class UF2Handler(Handler):
    NAME = "uf2"
    PATTERNS = [HexString("55 46 32 0A 57 51 5D 9E")]
    EXTRACTOR = UF2Extractor()
    DOC = HandlerDoc(
        name="UF2",
        description="USB Flashing Format: 512-byte blocks, each carrying a payload for a target address, used by RP2040/RP2350, ESP32-S2/S3 (TinyUF2), nRF52 and SAMD bootloaders.",
        handler_type=HandlerType.ARCHIVE,
        vendor="Microsoft",
        references=[
            Reference(
                title="UF2 specification",
                url="https://github.com/microsoft/uf2",
            ),
            Reference(
                title="UF2 family IDs",
                url="https://github.com/microsoft/uf2/blob/master/utils/uf2families.json",
            ),
        ],
        limitations=[
            "One file per contiguous address region; gaps are not padded",
            "File-container blocks (flag 0x1000) are not reassembled into files",
        ],
    )

    def calculate_chunk(self, file: File, start_offset: int) -> ValidChunk | None:
        file.seek(start_offset)
        end = start_offset
        while True:
            raw = file.read(BLOCK_SIZE)
            if parse_block(raw) is None:
                break
            end += BLOCK_SIZE
        if end == start_offset:
            raise InvalidInputFormat("no valid UF2 block at the match")
        return ValidChunk(start_offset=start_offset, end_offset=end)
