# unblob-installer-handlers

An [unblob](https://github.com/onekey-sec/unblob) plugin that adds nine
handlers: four for MCU firmware containers and five for Windows installers.
Install it next to unblob and the handlers are found through unblob's plugin
entry point. unblob carves their chunks and recurses into what they extract,
so there is no separate tool to learn.

| Handler | Format | Output |
|---|---|---|
| `uf2` | UF2 | one `.bin` per family and contiguous address region |
| `ihex` | Intel HEX, also when embedded in binary data | one `.bin` per contiguous address region |
| `dfuse` | ST DfuSe `.dfu` | one `.bin` per target element |
| `mcuboot` | MCUboot images (little-endian) | header, image and TLV area; image metadata in unblob's report |
| `installshield` | InstallShield version 5 `data1.cab` | the cabinet's files (`unshield`) |
| `installshield_set` | a directory holding an InstallShield cabinet set, version 5 or 6 and later | the set's files (`unshield`) |
| `installshield_setup` | the package a single-file InstallShield `setup.exe` carries (`InstallShield` and `ISSetupStream` layouts) | its members (MSI, cabinets, `Setup.ini`, …) de-obfuscated and inflated, unpacked further by unblob |
| `inno` | Inno Setup 5.1.5–7.1 installers | the installer's files (`innoextract`) |
| `setup_factory` | Setup Factory 7–10 installers | the installer's files (`sfextract`) |
| `wix_burn` | WiX Burn bundles | the UX and attached containers as `.cab`, unpacked further by unblob |
| `cyacd` | Cypress `.cyacd` (PSoC 3/4/5LP bootloader) | per flash array, one `.bin` per run of contiguous rows at row number × row length; silicon ID in unblob's report |
| `cyacd2` | Infineon `.cyacd2` (DFU SDK, PSoC 4/6) | one `.bin` per contiguous address range; header values, `@APPINFO` and encryption (`@EIV`, written as stored) in unblob's report |
| `installshield_plain` | a single-file InstallShield `setup.exe` whose files follow the PE image unencrypted (ANSI or UTF-16 "plain" layout, no package header) | each file under its destination name, e.g. `Disk1/data1.hdr`; an InstallShield set among them is unpacked further by `installshield_set` |
| `nsis` | Nullsoft (NSIS) installers | the installer's files (`7z`), after its CRC is checked (a mismatch is reported) |
| `gbl` | Silicon Labs GBL v3 (Gecko Bootloader) | one `.bin` per contiguous address range of the program data; other tags as `tag_0x<id>_<n>.bin`; encrypted images as raw tags |
| `zigbee_ota` | Zigbee OTA upgrade files | one `tag_0x<tag>_<n>.bin` per sub-element, unpacked further by unblob; header fields in unblob's report |

The firmware containers are written without fill bytes: a gap in the address
space is a gap between files, and the base address is in each file name
(`0x10000000.bin`).

## Requirements

- Linux x86-64, CPython 3.10–3.14.
- unblob **26.6.4**. The package pins it.
- For the installer formats, these tools on `PATH`:

| Command | Needed for | Version |
|---|---|---|
| `unshield` | InstallShield | 1.6.2 |
| `innoextract` | Inno Setup | upstream PR [#210](https://github.com/dscharrer/innoextract/pull/210) at `376a13e7`; the packaged 1.9 fails on Inno Setup 6.4.3 and later |
| `sfextract` | Setup Factory | the fork [`Ext745/sfextract`](https://github.com/Ext745/sfextract) at `33399fae` (Setup Factory 7–10 fixes, offered upstream as [CybercentreCanada/sfextract#12](https://github.com/CybercentreCanada/sfextract/pull/12)) |
| `7z` | NSIS installers (`nsis`); unblob's own CAB handler, for Burn containers | 7-Zip 26.00 (FSD C-04) |

UF2, Intel HEX, DfuSe, MCUboot, Zigbee OTA, GBL, `.cyacd`/`.cyacd2`,
single-file InstallShield setup files and WiX/Burn need no external tool.
[`.devcontainer/Dockerfile`](.devcontainer/Dockerfile) builds all of them.

## Installation

The package is not on PyPI. Install it into the same environment as unblob:

```sh
pip install git+https://github.com/Ext745/unblob-installer-handlers
```

or from a checkout with `pip install .`. Releases attach a wheel to the
GitHub release page. Check that unblob sees the handlers and their tools:

```sh
unblob --show-external-dependencies
```

## Usage

Run unblob as usual; the handlers have no options of their own:

```sh
unblob -e out/ --report report.json updater.exe
```

## Limitations

- **NSIS** support carries the NSIS code of unblob PR
  [#1255](https://github.com/onekey-sec/unblob/pull/1255) (MIT, ONEKEY GmbH;
  module headers name the commit). 7-Zip does not verify the installer CRC;
  the handler does and reports a mismatch.
- **Single-file InstallShield** (`installshield_setup`) carries the code of
  unblob PR [#1707](https://github.com/onekey-sec/unblob/pull/1707) (MIT,
  ONEKEY GmbH; the module header names the commit). Layout types 5 and
  later are not recognised, and member names that would land outside the
  extraction directory are skipped and reported.
- **Handler order with #1255.** Loaded as plugins together, this package's
  Inno Setup, Setup Factory and Burn handlers claim their installers. In an
  unblob that has #1255 merged, its generic `pe` handler is asked first and
  takes the whole installer as a plain PE. This has been reported on #1255.
- InstallShield version 6 and later is handled only as a set, not as a lone
  `data1.cab` or `data1.hdr`.
- MCUboot signatures are not verified, and encrypted payloads are not
  decrypted.

The full list is in the [user manual](docs/UserDocumentation/User-Manual.md#5-limitations).

## Upstream

Each handler is meant to land in unblob itself. This plugin works with stock
unblob in the meantime.

| Handler | unblob PR |
|---|---|
| UF2 | [#1687](https://github.com/onekey-sec/unblob/pull/1687) |
| MCUboot | [#1688](https://github.com/onekey-sec/unblob/pull/1688) |
| InstallShield | [#1689](https://github.com/onekey-sec/unblob/pull/1689) |
| Intel HEX, DfuSe | not opened yet |
| Inno Setup, Setup Factory, WiX/Burn | not opened yet |

## Documentation

- [User manual](docs/UserDocumentation/User-Manual.md): installation, the
  output layout per format, limitations, troubleshooting.
- [Functional specification](docs/Functionality/unblob-installer-handlers-fsd.md):
  every requirement and how it is verified.
- The project's working records: [`PLAN.md`](PLAN.md) (progress per handler),
  [`testing/test-plan.yaml`](testing/test-plan.yaml) (every test and its last
  result), and [`docs/Method/`](docs/Method/) (how it was built and tested).

## Licence

MIT, see [`LICENSE`](LICENSE). No code is taken from GPL or reciprocal-licence
sources; format facts from documented sources are cited in the modules that
use them.
