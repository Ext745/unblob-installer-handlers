# 0001 — Ship as an unblob plugin, not a standalone tool

**Date:** 2026-10-24 · **Status:** accepted · **Proposed by:** human

*Backfilled from `PLAN.md`, FSD §4.4 and project notes.*

## Context
Upstream may not prioritise these handlers, and analysts already use unblob.

## Decision
Ship the handlers as a plugin found through unblob's entry point, and contribute them upstream as well.

## Alternatives considered
- A standalone tool or a UniExtract2 port: out of scope, FSD §4.4.

## Consequences
Users get the handlers regardless of upstream merges. Pinned to one unblob version.
