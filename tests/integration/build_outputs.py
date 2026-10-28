"""Write each __input__'s expected __output__ (FSD C-09).

Usage, inside the dev container: `python -m tests.integration.build_outputs`.
The extraction is the one TC-CON-14 compares against; review the diff before
committing it, since this records whatever the handlers do today.
"""

import shutil

from unblob.testing import check_result

from tests.conftest import INTEGRATION, run_unblob


def main() -> None:
    for input_dir in sorted(INTEGRATION.glob("**/__input__")):
        output_dir = input_dir.parent / "__output__"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir()
        for input_file in sorted(input_dir.iterdir()):
            check_result(run_unblob(input_file, output_dir))
        if not any(output_dir.iterdir()):
            (output_dir / ".gitkeep").touch()
        print(output_dir.relative_to(INTEGRATION))  # noqa: T201 - progress for the person running it


if __name__ == "__main__":
    main()
