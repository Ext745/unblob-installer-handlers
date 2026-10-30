"""Extraction failure rules shared by every handler (FSD §17).

A failed extraction raises ExtractError with an error report (FR-COM-03),
a missing external command is reported as such (FR-COM-04), and scratch
files stay inside the extraction directory (FR-COM-06).
"""

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from unblob.file_utils import InvalidInputFormat
from unblob.models import ExtractError, File, ValidChunk
from unblob.report import ExtractorDependencyNotFoundReport, UnknownError


def run_tool(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run an extractor's command; a missing command is a dependency report."""
    try:
        return subprocess.run(command, capture_output=True, check=False)
    except FileNotFoundError:
        raise ExtractError(
            ExtractorDependencyNotFoundReport(dependencies=[command[0]])
        ) from None


def scratch_dir(outdir: Path) -> tempfile.TemporaryDirectory[str]:
    """Make a temporary directory inside outdir, removed when the block ends.

    The `unblob` command runs extraction in a Landlock sandbox that allows
    writes only beneath the extraction root; the system temp directory is
    outside it (FR-COM-06).
    """
    outdir.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=outdir, prefix=".unblob-installers-")


def require_whole_chunk(
    calculate_chunk: Callable[[File, int], ValidChunk | None], inpath: Path
) -> None:
    """Refuse to extract input that is not exactly one chunk of this handler.

    unblob hands an extractor the chunk it carved, so this only fails when
    the input was cut short or altered; extracting it would write partial
    output and report success.
    """
    size = inpath.stat().st_size
    problem = "the input is empty"
    if size:
        with File.from_path(inpath) as file:
            try:
                chunk = calculate_chunk(file, 0)
            except InvalidInputFormat as exc:
                problem = str(exc)
            else:
                if chunk is not None and chunk.end_offset == size:
                    return
                problem = f"the input is not one whole chunk ({size} bytes)"
    raise ExtractError(UnknownError(exception=InvalidInputFormat(problem)))
