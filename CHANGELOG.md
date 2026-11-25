# Changelog

All notable changes to this package. Versions follow
[Semantic Versioning](https://semver.org/); while the version is below 1.0,
a minor version adds handlers or changes behaviour, and a patch version
fixes defects. Each release on the
[releases page](https://github.com/Ext745/unblob-installer-handlers/releases)
carries the wheel and the sdist that its release workflow verified.
Requirement IDs (FR-…, NFR-…) refer to the
[functional specification](docs/Functionality/unblob-installer-handlers-fsd.md).

## [0.2.0] — 2026-11-25

Seven handlers added, sixteen in total. Still pinned to unblob 26.6.4.

### Added

- `zigbee_ota`: Zigbee OTA upgrade files. One file per sub-element, which
  unblob unpacks further; header fields in unblob's report.
- `gbl`: Silicon Labs GBL v3 (Gecko Bootloader). One `.bin` per contiguous
  address range of the program data, with LZ4 and LZMA tags decompressed;
  other tags written as `tag_0x<id>_<n>.bin`. Encrypted images are written
  as raw tags.
- `cyacd`: Cypress `.cyacd` (PSoC 3/4/5LP bootloader). Silicon ID in
  unblob's report.
- `cyacd2`: Infineon `.cyacd2` (DFU SDK, PSoC 4/6). Header values,
  `@APPINFO` and encryption fields in unblob's report; encrypted data is
  written as stored.
- `installshield_setup`: the package a single-file InstallShield
  `setup.exe` carries (`InstallShield` and `ISSetupStream` layouts),
  de-obfuscated and inflated. Carries the code of unblob PR
  [#1707](https://github.com/onekey-sec/unblob/pull/1707) (MIT, ONEKEY GmbH).
- `installshield_plain`: single-file InstallShield installers whose files
  follow the PE image unencrypted (ANSI or UTF-16 "plain" layouts). A
  cabinet set among them is unpacked further by `installshield_set`.
- `nsis`: Nullsoft (NSIS) installers, extracted with `7z` after the
  installer's CRC is checked; a mismatch is reported. Carries the NSIS code
  of unblob PR [#1255](https://github.com/onekey-sec/unblob/pull/1255) (MIT,
  ONEKEY GmbH).

### Security

- Memory bounds for hostile input in the new handlers: GBL LZ4/LZMA
  decompression capped per tag (NFR-SEC-07, NFR-SEC-09); inflating an
  InstallShield single-file member allocates at most 1 MiB whatever its size
  (NFR-SEC-11, from a maintainer's review of #1707); member names that would
  land outside the extraction directory are skipped and reported
  (NFR-SEC-08).
- Assembling address-range files (UF2, Intel HEX, `.cyacd`/`.cyacd2`, GBL)
  allocates in proportion to the output rather than per byte written, and a
  conflict between two writes names both of them (NFR-SEC-10).

## [0.1.2] — 2026-11-18

### Fixed

- InstallShield: malformed version 5 cabinets (a forged `ISc(` header, or a
  descriptor inside the volume header or shorter than `unshield` reads) are
  no longer claimed (FR-ISC-07, FR-ISC-08). Found by an outside review of
  unblob PR [#1689](https://github.com/onekey-sec/unblob/pull/1689).
- InstallShield sets: a set with a missing or invalid volume, for example
  `data1.cab` and `data3.cab` without `data2.cab`, is reported instead of
  the volumes after the gap being dropped silently (FR-ISC-09).

## [0.1.1] — 2026-10-30

### Fixed

- Through the `unblob` command, Inno Setup and InstallShield extraction
  failed with "No usable temporary directory": unblob's Landlock sandbox
  blocked the handlers' scratch files. Scratch copies now live inside the
  extraction directory (FR-COM-06).

## [0.1.0] — 2026-10-30 — superseded, do not use

First release: nine handlers. `uf2`, `ihex`, `dfuse` and `mcuboot` for MCU
firmware containers; `installshield`, `installshield_set`, `inno`,
`setup_factory` and `wix_burn` for Windows installers.

Through the `unblob` command, Inno Setup and InstallShield extraction fails
in this version; use 0.1.1 or later.

[0.2.0]: https://github.com/Ext745/unblob-installer-handlers/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/Ext745/unblob-installer-handlers/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Ext745/unblob-installer-handlers/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Ext745/unblob-installer-handlers/releases/tag/v0.1.0
