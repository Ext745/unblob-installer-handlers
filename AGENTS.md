# AGENTS.md: Operating Manual for AI Agents

Read this before doing anything. `CLAUDE.md` is a symlink to this file.

## Project context (read, don't duplicate)
| File | Purpose |
|---|---|
| `GOAL.md` | Goal, constraints, **non-goals**, acceptance criteria |
| `STATUS.md` | Current state. **Read at session start, update at session end.** |
| `TESTING.md` | Real-hardware test rigs and soak log |
| `docs/00-Overview.md` | Plane map and authority order. The FSD defines the target. |
| `docs/Functionality/unblob-installer-handlers-fsd.md` | Requirements, security profile, verification contracts |
| `docs/Method/` | The loop every change follows, and the standards |
| `PLAN.md` | Project plan and handler progress |
| `testing/test-plan.yaml` | Every test, what it verifies, its last result |
| `testing/gates/` | Phase gates |
| `docs/decisions/` | Decision records. Don't reverse one without raising it first. |
| [APPROACH.md](https://github.com/Ext745/.github/blob/main/APPROACH.md) | How these projects are run (central) |
| [AI_POLICY.md](https://github.com/Ext745/.github/blob/main/AI_POLICY.md) | AI usage policy (central) |

## Commands
```bash
make build        # build
make test         # unit/integration tests (also run in CI)
make hil          # hardware-in-the-loop, needs target hardware attached
make scrub-check  # personal-data scan of tracked files
make prepublish   # full pre-publication check (history included)
# Long runs are started by the human: make soak RIG=A HOURS=72 SOAK_CMD="..."
```
- `make build`: creates `.venv` and installs the package with its pinned dev tools.
- `make test`: scrubber self-test, then ruff, pyright and pytest, as `ci.yml` does.
- `make hil`: the journey tests (`pytest -m journey`). Needs the real-file store and the project's runner.

A green `Hygiene` run proves scans only, never the handlers.

## Working rules
1. **Start** by reading `STATUS.md` and `GOAL.md`.
2. Work toward the acceptance criteria. Respect the non-goals.
3. Bold or unconventional approaches are welcome. Explain them. If you change direction or make a non-obvious choice, add a decision record in `docs/decisions/`.
4. Exploratory or abandoned work goes in `lab/<YYYY-MM-DD>-<topic>/` with a `NOTES.md`. Don't delete anything from `lab/`.
5. **Never claim hardware verification.** You may report: "builds", "unit tests pass", "not tested on hardware". Maturity levels and TESTING.md results come from real runs and are set by the human. Don't edit soak rows.
6. State plainly what you couldn't verify, and why.
7. Note any new dependency and the reason for it in STATUS.md or a decision record.
8. **End** every session by updating `STATUS.md`: what changed, what's untested, next steps, and **which model/tool you are** (e.g. "agent: Claude Opus 5.5 via Claude Code").
9. Commits: short imperative subject line. AI-assisted commits include a `Co-Authored-By` trailer.

## Personal data and secrets
This repo may be private now, but assume it will be public. **Git history goes public with it.**
- Never commit keys, passwords, APN credentials, WireGuard configs, `.env` files, or tokens.
- Before committing logs or raw output (to `lab/` or `tests/`), run `python3 tools/scrub.py --in-place <file>`. Modem logs contain IMEI/IMSI/ICCID and phone numbers. Network logs contain keys and public IPs.
- If the pre-commit scrub check flags something, fix the data. Don't bypass the hook. Mark a line `scrub:allow` only for genuine false positives, and say so in the commit message.

## Safety
*Inferred:* a host-side Python plugin with no electrical hazard. Input files are hostile by assumption (FSD §18): anything that parses them must not write outside the extraction directory, or hang.
Any change affecting these must be flagged **SAFETY REVIEW NEEDED** in the commit message and in STATUS.md, citing the relevant datasheet or reference. It can't be applied to hardware until the human has reviewed it.

## Out of bounds
- No PRs, issues, or comments on other people's repositories unless explicitly told to (see AI_POLICY).
- Don't rewrite git history on shared branches.
- Don't change repo visibility or settings.

## Code conventions
Python, using unblob's own ruff and pyright configuration (FSD C-05). See `docs/Method/`. Don't translate code from UniExtract2's GPL sources (FSD §4.4).
