# 0006 — Pull requests run on a GitHub-hosted runner

**Date:** 2026-11-25 · **Status:** accepted · **Proposed by:** agent, accepted by the owner (commit `baacb65`)

## Context
`ci.yml` ran every job on the project's own runner next to the bench (0004). Once the repo is public, a pull request from a fork would run its code on that runner.

## Decision
The `pull-request` job in `ci.yml` runs ruff, pyright and the unit tier on `ubuntu-24.04`, with no secrets and read-only contents. Pushes to `main` keep the bench runner, which also runs the integration tier: it needs `unshield`, `innoextract` and `sfextract` at pinned versions. This narrows 0004: hosted jobs are now hygiene scans plus the pull-request checks, and a hosted run is still never evidence about the handlers.

## Alternatives considered
- Keep PRs on the bench runner with manual approval for forks: one wrong click runs a stranger's code on the bench PC.
- Install the pinned extractors on the hosted runner: more setup for a tier that runs anyway after the merge.

## Consequences
While the repo is private, hosted jobs use the account's Actions minutes. On 2026-11-25 GitHub refused to start them ("recent account payments have failed or your spending limit needs to be increased", probe PR #2), so PRs get no check until billing is fixed or the repo is public, where hosted runners are free.
