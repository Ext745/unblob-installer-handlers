# Status

**Updated:** 2026-11-25 · **Maturity:** `experimental` · **Visibility:** private

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
1. Fix GitHub billing, or flip the repo public, then re-run probe PR #2 and close it.
2. Before going public: `make prepublish`; decide whether internal docs stay public; decide on rewriting the commit email (destructive, before the flip).
3. After the flip: enable private vulnerability reporting (`SECURITY.md` points to it).
4. Next release: run `full.yml`, record from its JUnit, one release review addendum covering changes since v0.2.0 (CI split, PR job, this kit).

## Session log
- 2026-11-25: repo kit landed on `main` as a merge of `repo-kit` (PR #1), so PR #1 closes as merged. Test files reformatted for `ruff format` with each `scrub:allow` kept on the line holding the version string. On this host: scrub, ruff, ruff format and pyright pass. pytest: 388 passed, 32 failed, because the devcontainer-built `.venv` has `/workspaces/...` shebangs (pyright, extractors) that don't resolve here. The runner's CI on `main` is the evidence. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: repo kit ported onto `main` after v0.2.0: conflicts in `ci.yml`, `.gitignore`, `CHANGELOG.md`, `README.md` resolved; STATUS, GOAL, TESTING, AGENTS updated to v0.2.0; decision 0006 added. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: v0.2.0 shipped, sixteen handlers. By: human + agent via Claude Code (from commit trailers)
- 2026-11-18: v0.1.2 shipped (InstallShield fixes). By: human + agent via Claude Code (from commit trailers)
- 2026-11-06: repo kit retrofit: added AGENTS.md, Makefile, tools, hooks, hygiene CI, GOAL, STATUS, TESTING, CHANGELOG, decisions. `tools/` is excluded from ruff and pyright, and added to TC-CON-05's allowed differences; lint rules are unchanged. By: agent: Claude Opus 5.5 via Claude Code
- 2026-10-30: v0.1.1 shipped, from `git log`. By: human + agent via Claude Code (from commit trailers)
