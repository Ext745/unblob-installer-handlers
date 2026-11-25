# Goal

> `docs/Functionality/`, `docs/Method/`, `testing/` and `PLAN.md` are kept in the project's internal repository and are not in the public one. References to them here, and FSD section and requirement IDs, point there.

*Inferred from `docs/Functionality/unblob-installer-handlers-fsd.md` and `PLAN.md`, which stay the authority. If this file and the FSD disagree, the FSD wins.*

## What I want to achieve
Let [unblob](https://github.com/onekey-sec/unblob) unpack formats it can't handle today: Windows installers and MCU firmware containers. They ship as a plugin, so users get them whether or not they merge upstream.

## Background
Firmware analysts often need to pull an image out of a vendor's Windows updater, and these are the containers that board build tools and vendors ship. This project was also the harness's first real pilot, run through the harness only.

## Constraints
- Platform: Linux x86-64, CPython 3.10 to 3.14, unblob 26.6.4 or later (tested version in `constraints.txt`).
- External tools: `unshield`, `innoextract`, `sfextract`, `7z` (NSIS).
- Licensing: no code translated from UniExtract2's GPL sources.
- Security: input files are hostile, the host is trusted (FSD §18).

## Non-goals
From FSD §4.4:
- A standalone extraction tool, a port of UniExtract2, or any use of Wine
- Game and resource archives
- Interactive features: password prompts, batch queues, a GUI
- UHARC, ISZ, Wise, Enigma VB
- InstallShield 3 `.Z` / `_sys1.cab`, VISE, Gentee (can be added later by change request)
- Motorola S-record, uImage, device tree, Matter OTA (binwalk handles them)
- LittleFS, SPIFFS, ESP-IDF FAT with wear levelling

## Acceptance criteria
"Done" comes from `testing/test-plan.yaml` and `testing/gates/`.

| # | Criterion | How it's verified | Done |
|---|---|---|---|
| 1 | Plugin registers its sixteen handlers, and each extracts its fixtures | Unit and integration tiers | ☑ *backfilled, unverified* |
| 2 | Handlers work on real vendor files | Real-file tier and journey | ☑ *backfilled, unverified* |
| 3 | Works through the `unblob` command, not only in-process | Journey, bench check on v0.2.0 | ☑ *backfilled, unverified* |
| 4 | Released with the journey run on the released files | Shipped gate, v0.2.0 | ☑ *backfilled, unverified* |
| 5 | Optional: handlers offered to unblob only if there is public interest after the repo is public. Handler order once #1255 merges is tracked separately (FR-PE-03) | FSD Phases 5 and 7 (optional since 0.27.0): C-07, FR-PE-03 | ☐ optional |

## References
- `docs/Functionality/unblob-installer-handlers-fsd.md`
- `PLAN.md`
- [unblob](https://github.com/onekey-sec/unblob)
