# 0004 — Hosted CI for hygiene checks only

**Date:** 2026-11-06 · **Status:** accepted · **Proposed by:** agent, same choice the owner accepted on the mqtt-heartbeat pilot

## Context
`ci.yml` keeps every job on the project's own runner, for hosted minutes among other reasons. 0006 later moved the pull-request checks to a hosted runner too. The repo kit's checks need no project tools.

## Decision
`hygiene.yml` runs the secret and personal-data scans hosted. Lint and tests stay on the project's runner. A hosted run is never evidence about the handlers.

## Alternatives considered
- Run hygiene on the project's runner: ties scans to its availability and its single-job concurrency.

## Consequences
Uses a few Actions minutes on a private repo; blocked by billing on 2026-11-25 (see 0006). The workflow is named `hygiene.yml` because `ci.yml` already exists.
