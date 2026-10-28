"""The FR-COM checks (FSD §17), shared by the tiers that run them.

Each takes one handler and one valid sample of it; the test modules decide
where the sample comes from (committed fixture or real-file store).
"""

import os
import random
from collections.abc import Iterator
from pathlib import Path

import pytest
from unblob.file_utils import File, InvalidInputFormat
from unblob.models import ExtractError, ValidChunk
from unblob.report import ErrorReport

from tests.conftest import chunks, run_unblob
from tests.samples import PATTERN_BYTES, handler

RANDOM_LEN = 4096


def check_false_candidate_declined(name: str, sample: Path, tmp_path: Path) -> None:
    """FR-COM-01: pattern bytes, random bytes, then a real sample later on."""
    rng = random.Random(1701)  # noqa: S311 - fixed test data, not cryptography
    decoy = PATTERN_BYTES[name] + rng.randbytes(RANDOM_LEN)
    combined = tmp_path / f"decoy-then-{sample.name}"
    combined.write_bytes(decoy + sample.read_bytes())

    found = chunks(run_unblob(combined, tmp_path / "x", max_depth=1))
    starts = [c.start_offset for c in found if c.handler_name == name]
    assert starts == [len(decoy)], f"{name} chunks start at {starts}"


def mutants(data: bytes, seed: int) -> Iterator[tuple[str, bytes]]:
    """16 evenly spaced truncations, then 1 000 single-byte mutations."""
    for i in range(16):
        cut = len(data) * i // 16
        yield f"truncated at {cut}", data[:cut]
    rng = random.Random(seed)  # noqa: S311 - fixed test data, not cryptography
    for _ in range(1000):
        at = rng.randrange(len(data))
        value = (data[at] + rng.randrange(1, 256)) % 256
        yield f"byte {at} = 0x{value:02x}", data[:at] + bytes([value]) + data[at + 1 :]


def check_chunk_calculation_contained(name: str, sample: Path) -> None:
    """FR-COM-02: only InvalidInputFormat may leave calculate_chunk."""
    under_test = handler(name)
    escaped = []
    for label, data in mutants(sample.read_bytes(), seed=len(name)):
        if not data:
            continue
        with File.from_bytes(data) as file:
            try:
                chunk = under_test.calculate_chunk(file, 0)
            except InvalidInputFormat:
                continue
            except Exception as exc:
                escaped.append(f"{label}: {type(exc).__name__}: {exc}")
                continue
        if chunk is not None:
            assert isinstance(chunk, ValidChunk)
            assert 0 <= chunk.start_offset < chunk.end_offset <= len(data), label
    assert not escaped, f"{len(escaped)} escaped, first: {escaped[:5]}"


def check_failed_extraction_raises(name: str, inpath: Path, tmp_path: Path) -> None:
    """FR-COM-03: a failing extractor raises ExtractError carrying an error report."""
    outdir = tmp_path / "out"
    outdir.mkdir()
    extractor = handler(name).EXTRACTOR
    assert extractor is not None
    with pytest.raises(ExtractError) as raised:
        extractor.extract(inpath, outdir)
    assert any(isinstance(r, ErrorReport) for r in raised.value.reports), (
        raised.value.reports
    )


def failing_tool(bin_dir: Path, tool: str) -> None:
    """Put an executable named tool on bin_dir that only fails (exit 3)."""
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / tool
    script.write_text('#!/bin/sh\necho "forced failure" >&2\nexit 3\n')
    script.chmod(0o755)


def path_without(tool: str, bin_dir: Path) -> str:
    """Build a PATH holding links to every executable on PATH except tool."""
    bin_dir.mkdir(exist_ok=True)
    for entry in os.environ["PATH"].split(os.pathsep):
        directory = Path(entry)
        if not directory.is_dir():
            continue
        for program in directory.iterdir():
            link = bin_dir / program.name
            if (
                program.name != tool
                and not link.exists()
                and os.access(program, os.X_OK)
            ):
                link.symlink_to(program)
    return str(bin_dir)
