# Changelog

Releases are tagged when the project reaches a new maturity level or a meaningful milestone.
Each entry links the soak runs that back it. Raw `output.log` files are attached to the GitHub release.

## [Unreleased]
- Repo kit: agent manual, Makefile, tools, hooks, hygiene CI, project state files, decision records.

## [v0.1.1] — 2026-10-30 — experimental
- Fix: Inno Setup and InstallShield failed through the `unblob` command, because its Landlock sandbox blocked a temp file.
- Evidence: bench check 9/9.

## [v0.1.0] — 2026-10-30 — experimental
- First release: nine handlers. Superseded by v0.1.1.

<!--
## [v0.2.0] — YYYY-MM-DD — soak-tested
- What changed
- Evidence: S-004 (72 h, rig A, ✅ pass), S-005 (168 h, rig A, ✅ pass)
-->
