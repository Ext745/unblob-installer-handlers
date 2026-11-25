# Contributing

Thank you for helping. Bug reports, real-world files a handler gets wrong,
and new handlers are all welcome. For a security problem, see
[SECURITY.md](SECURITY.md) instead of opening an issue.

## Reporting a problem

Open an issue with:

- the package and unblob versions (`pip show unblob-installer-handlers unblob`);
- the command you ran and unblob's report (`--report report.json`);
- where the file comes from (a vendor download link is ideal). Please do not
  attach files you may not redistribute; a link or a description is enough.

## How this project works

Every behaviour is written down as a requirement before it is coded. The
[functional specification](docs/Functionality/unblob-installer-handlers-fsd.md)
(the FSD) states what each handler must and must not do, with a
verification contract for each requirement. `testing/test-plan.yaml` lists
every test, the requirements it verifies, and its last result.

So a change that adds or alters behaviour starts in an issue: describe what
the handler should do, and the FSD and test plan are updated to match. A
fix that makes a handler meet an existing requirement can go straight to a
pull request. The [Method docs](docs/Method/) describe the full workflow.

## Development setup

The devcontainer (`.devcontainer/`) builds every external tool at the
version the package expects. A plain virtual environment also works; the
installer formats then need their tools on `PATH` (see the README's
requirements):

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

This installs unblob 26.6.4 (pinned) and the pinned `pytest`, `ruff` and
`pyright`. Supported Python versions are 3.10 to 3.14, so do not use
features newer than 3.10, in tests too.

## Checks

Run these before opening a pull request. They are the same as CI's:

```sh
.venv/bin/ruff check .
.venv/bin/ruff format --check .
PYRIGHT_PYTHON_IGNORE_WARNINGS=1 .venv/bin/pyright --pythonpath .venv/bin/python
.venv/bin/pytest -q tests/unit tests/integration
```

- **ruff and pyright** use unblob's own configuration unchanged (FSD C-05).
  Do not add local overrides; `tests/unit/test_constraints.py` checks that.
- **Real-file and journey tests** (`tests/realfile/`, `tests/journey/`) run
  against vendor files that cannot be redistributed. They skip when the store
  is absent; the maintainer runs them before each release.
- While working, running only the tests of the handler you change is fine.

## Code

- **One module per handler** in `src/unblob_installers/`, shaped like
  unblob's own handlers (`NAME`, `PATTERNS`, `EXTRACTOR`, `DOC`,
  `calculate_chunk()`), so it can move into unblob unchanged. A handler never
  imports another handler; shared code lives in the `_`-prefixed modules.
  [`docs/Method/project/architecture.md`](docs/Method/project/architecture.md)
  has the details.
- **Treat every input as hostile.** Bound what a file can make a handler
  allocate or write, and keep every output path inside the extraction
  directory (FSD §18).
- **Tests come with the change.** Each test is declared in
  `testing/test-plan.yaml` with the requirement it verifies, and checks what
  must *not* happen as well as what must.

## Licensing — please read

The package is MIT-licensed. Contributions are accepted under the same
licence.

- **No code from GPL or reciprocal-licence sources** (UniExtract2, GPL
  tools, MS-RL code such as WiX's source), not even translated (FSD C-06).
- **Format facts may come from any documented source**: field layouts,
  constants, magic values and offset rules. Cite the source in the module
  that uses them.
- **Code carried from an unblob pull request** names the PR, the commit, the
  authors and the MIT licence in the module header (FSD C-12).

## Test fixtures

Fixtures live in `tests/integration/<category>/<handler>/__input__/`, in
unblob's layout, with the expected output beside them in `__output__`
(FSD C-09). Each one:

- is built by `tests/fixtures/build.sh` from the shared test payload, or is
  otherwise redistributable under MIT;
- has a row in [`tests/fixtures/SOURCES.md`](tests/fixtures/SOURCES.md)
  with its source, licence and build command (C-08);
- is 1 MiB or smaller, unless listed there as an exception with its reason
  (C-10).

Regenerate the expected output with `python -m tests.integration.build_outputs`.

## Pull requests

Keep a pull request to one handler or one fix, and say which requirement it
implements or fixes. CI on a pull request runs lint, types and the unit
tier on a GitHub-hosted runner; the integration, real-file and journey tiers
need the pinned extractors and the real-file store, and run on the project's
own runner after the merge.
