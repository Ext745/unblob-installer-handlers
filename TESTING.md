# Testing

> `docs/Functionality/`, `docs/Method/`, `testing/` and `PLAN.md` are kept in the project's internal repository and are not in the public one. References to them here, and FSD section and requirement IDs, point there.

Code in this repo is verified by running it on real files and through the real `unblob` command, not just by unit tests. `testing/test-plan.yaml` stays the source of truth for test results; this file records rigs and long runs.

## Test rigs
| Rig | Hardware | Firmware / OS | Peripherals / setup | Notes |
|---|---|---|---|---|
| A | x86-64 Linux PC, project's self-hosted runner | Linux, Python 3.10 to 3.14, unblob 26.6.4 | Real-file store, external extractors | Runs every tier |
| B | RP2040 B2, ESP32-S3, classic ESP32 on the Embedded AI Harness bench | Board builds | Flash and serial through the bench | Proves file provenance only |

## Soak / long-run log
Rows are added by `tools/soak.py --append` (or by hand for runs made before the tool existed; mark those *backfilled*).

| ID | Start | Duration | Rig | Commit | Configuration | Result | Notes |
|---|---|---|---|---|---|---|---|

**Cumulative real-hardware runtime:** 0.0 h

No soak has been recorded. This is a host-side plugin that runs per file, so test breadth matters more than hours.

Result key: ✅ pass (clean) · ⚠️ degraded (completed, with errors / resets / restarts / leak) · ❌ fail (process died)

## Sessions
Rows up to 2026-10-30 are *backfilled, unverified*: copied from `testing/test-plan.yaml`, `PLAN.md` and commit messages, nothing re-run. Later rows are copied from `PLAN.md`'s release records.

| Date | Rig | Commit | What ran | Recorded result |
|---|---|---|---|---|
| 2026-10-24 | B | Not recorded | Boards booted the firmware behind the test files | Marker seen on all three |
| 2026-10-30 | A | `b6cfe5e` | Journey | 7 passed |
| 2026-10-30 | A | `552271a` | Release dry run | Journey green |
| 2026-10-30 | A | v0.1.1 | Bench check through the `unblob` command | 9/9 |
| 2026-11-18 | A | v0.1.2 | Release run 44450916929: journey on the wheel | 7 passed |
| 2026-11-19 | A | v0.1.2 | Bench check through the installed `unblob` command, one real file per format | All exit 0, outputs match their oracles |
| 2026-11-25 | A | v0.2.0 | Release run 45529483286: journey on the wheel | 17 passed |
| 2026-11-25 | A | v0.2.0 | Bench check through the installed `unblob` command, one real file per new format | All exit 0, chunk from the intended handler |

## Issues found by real-world testing
*Backfilled, unverified.*

| Found in | Symptom | Cause | Fixed in |
|---|---|---|---|
| v0.1.0 | Inno and InstallShield failed through the `unblob` command | Landlock sandbox blocked a temp file in `/tmp`; tests had bypassed the sandbox | v0.1.1 |

## Automated tests
- `make test`: scrubber self-test, ruff, pyright and pytest
- `gh workflow run full.yml`: the full suite on the project's runner, whose JUnit report records plan statuses (started by hand before a gate check)
- `make hil`: journey tests, need the real-file store
- `make soak RIG=A HOURS=72 SOAK_CMD="..."`: long run with logging, see `tools/soak.py --help`

## Maturity criteria for this project
Criteria vary by project, and there's no single fixed value. The owner sets the level.
- `bench-tested`: journey green on the released files
- `soak-tested`: days of logged runtime across the project's normal tests, such as repeated runs over the real-file store
- `stable`: soak-tested, in regular use, no open critical issues
