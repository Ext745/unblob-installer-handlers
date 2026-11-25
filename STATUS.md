# Status

> `docs/Functionality/`, `docs/Method/`, `testing/` and `PLAN.md` are kept in the project's internal repository and are not in the public one. References to them here, and FSD section and requirement IDs, point there.

**Updated:** 2026-11-25 · **Maturity:** `experimental` · **Visibility:** private (internal repo); public copy created 2026-11-25, still private

## Summary
v0.2.0 is released, with sixteen handlers: eight for MCU firmware containers and eight for Windows installers. 223 of 226 planned tests are recorded as passing. The other 3 are FSD Phase 5 (upstream, after shipment) and don't limit the shipped plugin: TC-PE-05/06 guard a future case (if unblob PR #1255 merges, its built-in `pe` handler would run before this plugin's), and TC-CON-07 checks that every handler has an upstream PR link (held until the repo is public).

## Verified on real hardware
A host-side plugin, so "real" here means real files on the project's runner. See `TESTING.md`.
- v0.2.0 release run 45529483286: journey 17 passed on the released wheel.
- Bench check on v0.2.0 after reinstalling it on the bench PC: one real file per new format through the installed `unblob` command, all exit 0 with the chunk from the intended handler (`PLAN.md`).
- Boards prove where the firmware test files came from: RP2040, ESP32-S3 and classic ESP32 on 2026-10-24.

## Implemented, not hardware-tested
- Handler order with #1255 merged: TC-PE-05 and TC-PE-06 not done.

## Known broken / limitations
- Hosted CI jobs (`hygiene.yml`, the `pull-request` job in `ci.yml`) can't start while the repo is private: GitHub reports a billing or spending-limit block (2026-11-25, probe PR #2). See `docs/decisions/0006-pull-requests-hosted.md`.
- Upstream PRs for the Phase 5 and Phase 7 handlers are on hold until the repo is public.

## Open questions
- `unblob==26.6.4` is an exact pin (FSD C-01). Installing the plugin beside a newer unblob will downgrade unblob or fail to resolve. 26.6.4 is still the latest on PyPI (checked 2026-11-25). Proposal waiting on the human: a lower bound plus a CI job against the newest unblob, as an FSD C-01 change with a decision record.

## Next steps
1. Review the public copy `Ext745/unblob-installer-handlers` (still private), then flip it public. That is the human's act. Its hosted jobs (hygiene, lint + unit tests) can't start until then, because of the billing block.
2. Close probe PR #2 on the internal repo (its hosted job stays blocked there); prove the hosted PR job with a throwaway PR on the public copy after the flip.
3. After the flip: enable private vulnerability reporting on the public repo (`SECURITY.md` points to it).
4. Next release: run `full.yml`, record from its JUnit, one release review addendum covering changes since v0.2.0 (CI split, PR job, this kit).

## Session log
- 2026-11-25: public copy set up (decision 0007). The repo was renamed to `Ext745/unblob-installer-handlers-internal`, and `.devcontainer/.env` `GH_REPO` was changed and the container recreated; the bench runner takes internal jobs (run 45598379977). `Ext745/unblob-installer-handlers` was created private and filled by `tools/export-public.sh --push --releases`, with releases v0.1.0 to v0.2.0 holding the same files (v0.2.0 wheel `c4cdff2f…227fcca4`, the harness's pin). A second export fast-forwarded, so syncs work. Sync after each internal push with `tools/export-public.sh --push`. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: `make prepublish`: gitleaks clean (319 commits). Real personal data: the owner's email in 634 commits and two board MACs in history. Everything else is a reviewed false positive (decision 0007). Chosen by the human: a public copy exported with rewritten history; `docs/Method/`, the FSD, `testing/` and `PLAN.md` stay internal; the full kit is public; hosted CI only there. Added `tools/export-public.sh` (dry run verified: 116 commits, 4 tags, no old email, MACs or internal paths); bench jobs guarded to the internal repo; TC-CON-07/11 skip without `PLAN.md`; public docs no longer link internal files. New tool dependency: git-filter-repo 2.47.0 (export only). Nothing pushed or renamed yet. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: `make test` and `make hil` pass `--basetemp` to pytest, defaulting to `~/.cache/unblob-installer-handlers/pytest` (override with `PYTEST_BASETEMP`), because pytest's temp dirs filled the 3.8 GB `/tmp` tmpfs on this PC. `ci.yml` and `full.yml` call pytest directly and are unchanged. Checked with `tests/integration/test_common.py` (15 passed, nothing written to `/tmp`). By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: repo kit landed on `main` as a merge of `repo-kit` (PR #1), so PR #1 closes as merged. Test files reformatted for `ruff format` with each `scrub:allow` kept on the line holding the version string. On this host: scrub, ruff, ruff format and pyright pass. pytest: 388 passed, 32 failed, because the devcontainer-built `.venv` has `/workspaces/...` shebangs (pyright, extractors) that don't resolve here. The runner's CI on `main` is the evidence. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: repo kit ported onto `main` after v0.2.0: conflicts in `ci.yml`, `.gitignore`, `CHANGELOG.md`, `README.md` resolved; STATUS, GOAL, TESTING, AGENTS updated to v0.2.0; decision 0006 added. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: v0.2.0 shipped, sixteen handlers. By: human + agent via Claude Code (from commit trailers)
- 2026-11-18: v0.1.2 shipped (InstallShield fixes). By: human + agent via Claude Code (from commit trailers)
- 2026-11-06: repo kit retrofit: added AGENTS.md, Makefile, tools, hooks, hygiene CI, GOAL, STATUS, TESTING, CHANGELOG, decisions. `tools/` is excluded from ruff and pyright, and added to TC-CON-05's allowed differences; lint rules are unchanged. By: agent: Claude Opus 5.5 via Claude Code
- 2026-10-30: v0.1.1 shipped, from `git log`. By: human + agent via Claude Code (from commit trailers)
