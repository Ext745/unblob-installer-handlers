# Status

**Updated:** 2026-11-06 · **Maturity:** `experimental` · **Visibility:** private

## Summary
v0.1.1 is released, with nine handlers. 127 of 130 planned tests are recorded as passing; the other 3 wait on upstream PR #1255 and FSD Phase 5.

## Verified on real hardware
A host-side plugin, so "real" here means real files on the project's runner. *Backfilled, unverified*: this retrofit read the records. See `TESTING.md`.
- Bench check on v0.1.1: 9/9.
- Boards prove where the firmware test files came from: RP2040, ESP32-S3 and classic ESP32 on 2026-10-24.

## Implemented, not hardware-tested
- Handler order with #1255 merged: TC-PE-05 and TC-PE-06 not done.

## Known broken / limitations
- TC-CON-07 not done: upstream merge verdicts for each handler.
- Inno, Setup Factory and Burn upstream PRs are on hold.

## In progress
- Repo kit retrofit, PR open.

## Next steps
1. Check upstream PRs #1687, #1688 and #1689.
2. Before going public: review history with `make prepublish`.

## Session log
- 2026-11-06: repo kit retrofit: added AGENTS.md, Makefile, tools, hooks, hygiene CI, GOAL, STATUS, TESTING, CHANGELOG, decisions. `tools/` is excluded from ruff and pyright, and added to TC-CON-05's allowed differences; lint rules are unchanged. By: agent: Claude Opus 5.5 via Claude Code
- 2026-10-30: v0.1.1 shipped, from `git log`. By: human + agent via Claude Code (from commit trailers)
