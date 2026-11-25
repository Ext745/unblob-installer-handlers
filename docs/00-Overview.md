# unblob Installer & MCU-Container Handlers — Documentation

> `docs/Functionality/`, `docs/Method/`, `testing/` and `PLAN.md` are kept in the project's internal repository and are not in the public one. References to them here, and FSD section and requirement IDs, point there.

Three planes, three questions, three readers. Every sentence belongs to exactly
one of them.

| Plane | Question | Directory | Reader |
|---|---|---|---|
| **WHAT** | What must be true of the system? | [`Functionality/`](Functionality/) | Anyone judging whether it is correct — reviewer, tester, future maintainer |
| **HOW** | How is it built and changed? | [`Method/`](Method/) | Whoever writes the next change, human or agent |
| **OPERATE** | How do I install and run it? | [`UserDocumentation/`](UserDocumentation/) | Whoever installs, drives, or recovers the running system |

**Authority order: the FSD defines the target; the Method defines the way there.**
On conflict the FSD wins on *what must be true*, the Method wins on *how to get
there*. User documentation describes the system as built — if it disagrees with
either it is stale, which means reality or the spec moved.

None of the three carries history or rationale narrative. History lives in
`git log`; the reasons for significant decisions live in [`decisions/`](decisions/).

## Where to start

| If you are… | Read |
|---|---|
| Making a change | [`Method/AI-Workflow.md`](Method/AI-Workflow.md) — the loop every change follows |
| Judging correctness | `Functionality/unblob-installer-handlers-fsd.md` — requirements, state model, verification contracts |
| Installing or running it | [`UserDocumentation/`](UserDocumentation/) |
| Wondering why | [`decisions/`](decisions/) for significant decisions, otherwise `git log` |

## Routing a new sentence

Ask in order; the first yes wins:

1. Externally observable and must be true → **Functionality**
2. Constrains how code is written or verified → **Method**
3. Tells a human how to run or recover the system → **UserDocumentation**
4. About collaborating with an AI assistant → `CLAUDE.md`, which is not a plane
5. Why a significant decision was made → `docs/decisions/`
6. Why any other change was made → the commit message

Two questions settle the hard cases. *Could a black-box tester verify it?* — yes
means WHAT. *Would it survive a rewrite in another language?* — no means HOW.

Worked examples: *"reconnects within 30 s"* and *"rejects oversized payloads with
`-1`"* are Functionality. *"One module per component"* and *"lower layers never
import higher ones"* are Method. *"Flash the SD card with Raspberry Pi Imager"*
is UserDocumentation.

## Decisions

A settled decision leaves its **effect** as present-state content in the plane
it governs — a load-bearing "must not" becomes a stated negative requirement —
and its reason in the commit message.

A significant decision also gets a record in [`decisions/`](decisions/): a change
of direction, an unconventional choice, or a rejected option someone might try to
bring back. The plane stays the authority on what is true; a record only says why.
A fossilised decision hinders new work once its environment has gone, so when that
happens, supersede the record rather than working around it.

## Writing rules

**Present-state.** Write what is true now, in the present tense. No history, no
rationale narrative, no temporal comparison. Delete on sight: "now uses",
"previously", "as of v2", "we decided to", "legacy", "this was changed because".
Version history belongs in `git log`; a dated revision-history table is the one
sanctioned exception, and only in the FSD.

**One canonical home.** Every fact is stated once. Anywhere else that needs it,
link. Two copies of a fact are two facts the moment one is edited, and the reader
has no way to tell which is current.

All three planes are present-state and single-home; `decisions/` sits outside them. Routing lives in the table
above and nowhere else — a second copy of the triage is the first thing to drift.
