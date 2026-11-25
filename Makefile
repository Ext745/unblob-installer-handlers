# Single entry point for humans, agents and CI.
# build, test and hil need the project's tools, so they run on the self-hosted
# runner in ci.yml and release.yml. Hosted hygiene.yml uses scrub-check only.

RIG      ?= A
HOURS    ?= 72
SOAK_CMD ?=
SOAK_ARGS ?=
# pytest's temp root: off /tmp (a small tmpfs here) and outside the repo.
# pytest empties it at the start of each run, so it never piles up.
PYTEST_BASETEMP ?= $(HOME)/.cache/unblob-installer-handlers/pytest

.PHONY: build test hil soak scrub-check prepublish audit setup

build:
	python3 -m venv .venv
	.venv/bin/pip install -q -e '.[dev]'

test:
	python3 tools/scrub.py --self-test
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .
	.venv/bin/pyright --pythonpath .venv/bin/python
	@mkdir -p $(PYTEST_BASETEMP)
	.venv/bin/pytest -q --basetemp=$(PYTEST_BASETEMP)

hil:
	@mkdir -p $(PYTEST_BASETEMP)
	.venv/bin/pytest -q -m journey --basetemp=$(PYTEST_BASETEMP)

soak:
	@test -n "$(SOAK_CMD)" || { echo 'usage: make soak RIG=A HOURS=72 SOAK_CMD="..." [SOAK_ARGS="--error-pattern ..."]'; exit 2; }
	python3 tools/soak.py --rig $(RIG) --hours $(HOURS) --append $(SOAK_ARGS) --cmd "$(SOAK_CMD)"

scrub-check:
	@git grep -Il '' -- . ':!tools/scrub.py' ':!*lock.json' ':!*.lock' ':!tests/realfile/test_setupfactory_real.py' | xargs -r python3 tools/scrub.py --check

prepublish:
	bash tools/prepublish.sh

# Audit ALL your GitHub repos (full history). Read-only. Report goes to ~/.cache/repo-audit/
audit:
	python3 tools/audit-all.py $(AUDIT_ARGS)

setup:
	@command -v gitleaks >/dev/null || { echo "gitleaks not found. Install it first: https://github.com/gitleaks/gitleaks/releases"; exit 1; }
	@command -v pre-commit >/dev/null || pipx install pre-commit || python3 -m pip install --user pre-commit
	pre-commit install --allow-missing-config   # hooks are shared: other branches may not have the config yet
