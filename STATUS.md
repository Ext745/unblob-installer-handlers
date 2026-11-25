# Status

> `docs/Functionality/`, `docs/Method/`, `testing/` and `PLAN.md` are kept in the project's internal repository and are not in the public one. References to them here, and FSD section and requirement IDs, point there.

**Updated:** 2026-11-25 · **Maturity:** `experimental` · **Visibility:** internal repo private; public copy `Ext745/unblob-installer-handlers` public since 2026-11-25

## Summary
v0.2.1 is released (2026-11-25; no handler changes since v0.2.0), with sixteen handlers: eight for MCU firmware containers and eight for Windows installers. 223 of 226 planned tests are recorded as passing. The other 3 are FSD Phase 5 (upstream, after shipment) and don't limit the shipped plugin: TC-PE-05/06 guard a future case (if unblob PR #1255 merges, its built-in `pe` handler would run before this plugin's). TC-CON-07 waits only for the next `full.yml` record: upstream PRs became optional in FSD 0.27.0, and it now passes when each handler has a PR link or is marked "not offered".

## Verified on real hardware
A host-side plugin, so "real" here means real files on the project's runner. See `TESTING.md`.
- v0.2.0 release run 45529483286: journey 17 passed on the released wheel.
- Bench check on v0.2.1 after reinstalling it on the bench PC (2026-11-25): one real file per handler through the installed `unblob` command, all exit 0 with the chunk from the intended handler; the InstallShield set 51/51 MD5 (`PLAN.md`).
- Bench check on v0.2.0 after reinstalling it on the bench PC: one real file per new format through the installed `unblob` command, all exit 0 with the chunk from the intended handler (`PLAN.md`).
- Boards prove where the firmware test files came from: RP2040, ESP32-S3 and classic ESP32 on 2026-10-24.

## Implemented, not hardware-tested
- Handler order with #1255 merged: TC-PE-05 and TC-PE-06 not done.

## Known broken / limitations
- The internal releases' sdists, v0.1.0 to v0.2.0, contain the internal records and the two board MACs. They stay internal; the public copy's releases carry only the wheels. Never attach them anywhere public.
- Hosted CI jobs can't start in the private internal repo: GitHub reports a billing or spending-limit block. On the public copy they run (probe PR #1, 2026-11-25: Hygiene and the hosted job passed). Earlier note: the block was seen (2026-11-25, probe PR #2). See `docs/decisions/0006-pull-requests-hosted.md`.
- Upstream PRs are optional (FSD 0.27.0): a handler is offered to unblob only if there is public interest after the repo is public.

## Open questions
- None. (The unblob pin was loosened on 2026-11-25, decision 0008.)

## Next steps
1. Watch the weekly `unblob latest` runs. When one is green on a newer unblob, bump the tested version (decision 0008).

## Session log
- 2026-11-25 (end of session):
  - **Allowlist:** also copied to Tvheadend_analog (PR #2, merged f4f7751), the only other public repo with the kit.
  - **Git identity:** the global `user.email` is now the GitHub noreply address. `sendemail.from` and a local `user.email` in hvr1950-fm and asm_unpack keep kernel patches on the real address.
  - **Open, for the human:** Tvheadend_analog's public history still has the personal email on 110 commits. Cleaning it means a history rewrite and force-push of a public repo.

  By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: `.prepublish-allow` support ported to the kit template: Ext745/project-template PR #7 (`scrub.py` fingerprints and allowlist with a self-test case, mutation-checked; `prepublish.sh` count; `TEMPLATE_USAGE.md`). Its CI passed, and it was merged as e22476c. The project-specific exclusion of `test_setupfactory_real.py` was not ported. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: private vulnerability reporting enabled on the public repo, as `SECURITY.md` describes. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: v0.2.1 reinstalled on the bench PC through the firmware-re `comp_install`, after commenting out the bench profile's stale 0.1.2 wheel override (`x86/harness.conf`, untracked; backup kept in the session scratchpad). Plugin 0.2.1 with the release wheel's hash, unblob 26.6.4, all 16 handlers and 4 extractors present. Bench check: one real file per handler through the installed `unblob` command, all claimed by the intended handler with no plugin error report. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: v0.2.1 released.
  - **Evidence:** full suite 45611010432 at 87b2c4b (452 passed, 7 xfailed); statuses recorded; review addenda U and F signed by the human; ready-for-shipment checked by the agent (not independently); dry run 45615542502.
  - **Release:** tag on 81c99be, release run 45617195455 (17 journey steps on the wheel). Files byte-identical to the artifact, and the sdist is clean. Copied to the public copy (Latest).
  - **Harness:** pin bumped in cacf278, host tests 1016 passed.

  Not reinstalled on the bench PC. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: unblob pin loosened, by the user (FSD 0.28.0, decision 0008).
  - **Package:** requires `unblob>=26.6.4`. `constraints.txt` pins the tested 26.6.4, used by `ci.yml`, `full.yml`, release verify, `make build` and TC-CON-02.
  - **New `unblob-latest.yml`:** weekly and on demand. Internal: pyright plus the unit and integration tiers on the bench. Public: pyright plus the unit tier, hosted.
  - **TC-CON-01** rewritten (floor, and tested version installed); its status is `not done` until the next `full.yml` run.
  - **First runs, by hand:** internal bench 45608964760 and public hosted 45608968261 both green (tested 26.6.4 = newest 26.6.4). `ci.yml` green in both repos.

  Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: the public copy went public, by the human's request.
  - **Ruleset 28071879:** no force-push or deletion on `main`.
  - **Probe PR #1 on the public copy:** Hygiene (45607678851) and the hosted lint, pyright and unit job (45607679102) passed, and the bench job was skipped. Closed, and its branch deleted.

  By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: `unblob.log` stripped from the public history (decision 0007); the public copy was force-pushed once, before the flip. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: sanity scan of the public copy (a fresh clone from GitHub).
  - **History:** clean apart from `unblob.log` (tracked until 2026-10-28), a debug log carrying local home-directory paths.
  - **Found and fixed:** every release sdist, v0.1.0 to v0.2.0, packed the internal records and the board MACs. Removed from the public releases (wheels checked clean, so they stay).
  - **Prevention:** `pyproject.toml` excludes the internal paths from the sdist (test build: 189 files, none internal). `export-public.sh --releases` refuses any file holding an internal path or a rewritten string; tested on the old sdist (refused), the wheel and the new sdist (both pass).

  Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: follow-ups.
  - **Prepublish allowlist:** `.prepublish-allow` holds 29 reviewed false positives, checked line by line. On the public export, `make prepublish` reports "Ready". The internal repo still flags its 6 real MAC lines, as it should.
  - **Small fixes:** `hygiene.yml` actions pinned by SHA; CONTRIBUTING explains how PRs flow; the public repo has a description and topics.
  - **New Makefile targets:** `make publish` / `publish-releases`.
  - **Host venv:** host `make test` gave ruff, format and pyright clean, pytest 406 passed and 15 failed. Every failure is a missing pinned extractor (`sfextract` fork, `innoextract` PR #210), which exist only in the container and on the runner.
  - **Ruleset:** saved in `tools/public-ruleset.json`; GitHub refuses it until the repo is public.

  `tools/scrub.py` and `tools/prepublish.sh` changed; the allowlist was ported to the kit template in Ext745/project-template PR #7. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: upstream made optional, by the user. FSD 0.27.0: C-07 drops from [Must] to [Should] and is met by a PR link, an unblob version or "not offered"; Phases 5 and 7 are marked optional. GOAL row 5 reworded, and ten PLAN.md PR cells now read "not offered". TC-CON-07 is no longer an xfail: it passes, and fails on an unmarked cell (checked by mutation). Its plan status waits for the next `full.yml` run. The test change goes into the next release review addendum. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: public copy set up (decision 0007). The repo was renamed to `Ext745/unblob-installer-handlers-internal`, and `.devcontainer/.env` `GH_REPO` was changed and the container recreated; the bench runner takes internal jobs (run 45598379977). `Ext745/unblob-installer-handlers` was created private and filled by `tools/export-public.sh --push --releases`, with releases v0.1.0 to v0.2.0 holding the same files (v0.2.0 wheel `c4cdff2f…227fcca4`, the harness's pin). A second export fast-forwarded, so syncs work. Sync after each internal push with `tools/export-public.sh --push`. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: `make prepublish`: gitleaks clean (319 commits). Real personal data: the owner's email in 634 commits and two board MACs in history. Everything else is a reviewed false positive (decision 0007). Chosen by the human: a public copy exported with rewritten history; `docs/Method/`, the FSD, `testing/` and `PLAN.md` stay internal; the full kit is public; hosted CI only there. Added `tools/export-public.sh` (dry run verified: 116 commits, 4 tags, no old email, MACs or internal paths); bench jobs guarded to the internal repo; TC-CON-07/11 skip without `PLAN.md`; public docs no longer link internal files. New tool dependency: git-filter-repo 2.47.0 (export only). Nothing pushed or renamed yet. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: `make test` and `make hil` pass `--basetemp` to pytest, defaulting to `~/.cache/unblob-installer-handlers/pytest` (override with `PYTEST_BASETEMP`), because pytest's temp dirs filled the 3.8 GB `/tmp` tmpfs on this PC. `ci.yml` and `full.yml` call pytest directly and are unchanged. Checked with `tests/integration/test_common.py` (15 passed, nothing written to `/tmp`). By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: repo kit landed on `main` as a merge of `repo-kit` (PR #1), so PR #1 closes as merged. Test files reformatted for `ruff format` with each `scrub:allow` kept on the line holding the version string. On this host: scrub, ruff, ruff format and pyright pass. pytest: 388 passed, 32 failed, because the devcontainer-built `.venv` has `/workspaces/...` shebangs (pyright, extractors) that don't resolve here. The runner's CI on `main` is the evidence. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: repo kit ported onto `main` after v0.2.0: conflicts in `ci.yml`, `.gitignore`, `CHANGELOG.md`, `README.md` resolved; STATUS, GOAL, TESTING, AGENTS updated to v0.2.0; decision 0006 added. Not tested on hardware. By: agent: Claude Opus 5.5 via Claude Code
- 2026-11-25: v0.2.0 shipped, sixteen handlers. By: human + agent via Claude Code (from commit trailers)
- 2026-11-18: v0.1.2 shipped (InstallShield fixes). By: human + agent via Claude Code (from commit trailers)
- 2026-11-06: repo kit retrofit: added AGENTS.md, Makefile, tools, hooks, hygiene CI, GOAL, STATUS, TESTING, CHANGELOG, decisions. `tools/` is excluded from ruff and pyright, and added to TC-CON-05's allowed differences; lint rules are unchanged. By: agent: Claude Opus 5.5 via Claude Code
- 2026-10-30: v0.1.1 shipped, from `git log`. By: human + agent via Claude Code (from commit trailers)
