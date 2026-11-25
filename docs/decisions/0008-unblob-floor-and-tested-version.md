# 0008 — unblob 26.6.4 or later, one tested version, newest tried weekly

**Date:** 2026-11-25 · **Status:** accepted · **Proposed by:** agent, chosen by human

## Context
The package required `unblob==26.6.4` (FSD C-01). The handlers use unblob's handler API and file utilities, which can change between releases, and an exact pin kept every test result tied to one unblob. But it also meant that installing the plugin next to a newer unblob downgrades unblob or fails to resolve. That gets worse with every unblob release.

## Decision
- **The package requires `unblob>=26.6.4`.** No upper bound: unblob uses calendar versions, so no version number signals a breaking change.
- **`constraints.txt` pins the tested version** (`unblob==26.6.4`). `ci.yml`, `full.yml`, the release verify job, `make build`, CONTRIBUTING and TC-CON-02's Python 3.10 venv all install with `-c constraints.txt`, so recorded results and release evidence stay tied to one unblob.
- **`unblob-latest.yml` runs weekly (Mondays) and on demand against the newest unblob.**
  - Internal repository: pyright, then the unit and integration tiers on the bench runner.
  - Public copy: pyright and the unit tier on a hosted runner.

  It records no plan statuses.
- **TC-CON-01** checks the floor requirement, that the tested version is at least the floor, and that the environment under test runs the tested version.
- **Moving the tested version** happens after a green weekly run on a newer unblob, in one commit that bumps:
  - `constraints.txt`;
  - the two `unblob==` pins in `.devcontainer/Dockerfile` (tools venv and the 3.10 wheelhouse);
  - the CHANGELOG.

  Then a `full.yml` run records the results.

## Alternatives considered
- **Keep the exact pin.** Rejected: users can't install the plugin next to a newer unblob.
- **A range with an upper bound** (`<27`). Rejected: calendar versions say nothing about compatibility, so the bound would be arbitrary.
- **No tested version, always the newest.** Rejected: test results would change with no change to this package, and a release's evidence couldn't be reproduced.

## Consequences
- A user on a newer unblob than the tested one runs an untested combination until the weekly job has tried it. The user manual says so and shows how to install the tested version.
- A red weekly run means a new unblob broke something. Fix the handler or state the limitation; don't tighten the requirement (FSD C-01).
- **Not covered:** the weekly job doesn't run the real-file or journey tiers on the newest unblob. Those still need a `full.yml` run after a bump.
- The released v0.2.0 wheel still requires `==26.6.4`. The floor applies from the next release.
- Not tested on hardware. No handler code changes.
