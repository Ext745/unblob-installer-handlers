# 0003 — Upstream work comes after shipment

**Date:** 2026-10-30 · **Status:** accepted · **Proposed by:** human

*Backfilled from FSD Phase 5 and project notes.*

## Context
The release gate depended on upstream PRs whose timing this project doesn't control, including #1255.

## Decision
Move C-07 and FR-PE-03 into FSD Phase 5, after shipment, so releases don't wait on upstream review.

## Alternatives considered
- Keep them in the gate: blocks releases indefinitely.

## Consequences
TC-PE-05, TC-PE-06 and TC-CON-07 stay not done until upstream moves.
