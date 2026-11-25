# 0007 — A public copy with its own history; the internal repository stays private

**Date:** 2026-11-25 · **Status:** accepted · **Proposed by:** agent, chosen by human

## Context
The repository is going public, and its git history goes public with it. `make prepublish` (2026-11-25) found:
- the owner's personal email as author and committer of 634 commits;
- two board MAC addresses in old versions of `testing/debugging-agenda.md` and `testing/test-plan.yaml`. They were redacted in the current files, but the history still has them.

The owner also wants the internal working records to stay private: `docs/Method/`, `docs/Functionality/` (the FSD), `testing/` and `PLAN.md`. Those records cite about 1,100 commit hashes, which any rewrite of this repository's history would break.

## Decision
- Rename this repository to `Ext745/unblob-installer-handlers-internal` and keep it private, with its history unchanged. It stays the source of truth: all work, the bench runner, the full suite and releases happen there.
- Publish a separate repository under the original name, `Ext745/unblob-installer-handlers`, built by `tools/export-public.sh` from the internal main branch and tags:
  - the internal paths are removed from every commit;
  - identities are rewritten to the GitHub noreply address;
  - the MACs are replaced.
- The rules holding the email and the MACs live in `.public-export/`, which is gitignored.
- The export is deterministic, so each sync is a fast-forward push.
- The public copy keeps the full repo kit (AGENTS.md, CLAUDE.md, STATUS.md, GOAL.md, TESTING.md, tools, hooks, hygiene CI). Files that mention internal paths say once that those paths are kept internally.
- CI on the public copy is GitHub-hosted only. In `ci.yml`, `full.yml` and `release.yml` the bench jobs run only when `github.repository` is the internal one. Releases are copied to the public copy with the same files (`--releases`), so the harness's SHA-256 pin and download URL still hold.
- TC-CON-07 and TC-CON-11 read `PLAN.md`, so they skip when it is missing.

## Alternatives considered
- **Rewrite this repository in place, and move the internal docs to a new private repository.** Rejected: every hash cited in the internal records would go stale, and a force-push on `main` is needed.
- **Rewrite in place for the email and MACs only, with all docs public.** Rejected: the internal docs would be public.
- **A fresh single-commit public repository.** Rejected: loses the public code history.

## Consequences
- **Two repositories.** A change reaches the public copy only when the export is run and pushed. Public pull requests are applied in the internal repository and then exported, never merged on the public side.
- **The rule files must never change for commits already exported.** A changed rule changes every later hash, and the next push would no longer fast-forward.
- **`make prepublish` on the public copy still reports false positives in history.** They were reviewed on 2026-11-25 and accepted:
  - version strings read as public IPs (for example `9.1.1.1`, `1.0.0.2`); <!-- scrub:allow version numbers -->
  - Intel HEX fixture data read as an IMEI;
  - `$GH_RUNNER_PAT`, a variable name with no value, read as a credential.

  gitleaks found no secrets in 319 commits.
- **The runner loop registers to `GH_REPO` in `.devcontainer/.env`.** It must name the internal repository before a public repository takes the original name.
- **New tool dependency:** `git-filter-repo` 2.47.0, used only by the export script, not by the package or its tests.
- Not tested on hardware. Nothing here changes handler code.
