# unblob Installer & MCU-Container Handlers — User Manual

How to install the handler plugin next to unblob and use it.

The plugin adds nine handlers to unblob 26.6.4: four for MCU firmware
containers (UF2, Intel HEX, DfuSe, MCUboot) and five for Windows installers
(InstallShield file and set, Inno Setup, Setup Factory, WiX/Burn). unblob
finds them, carves their chunks and recurses into what they extract — there
is no separate tool to learn.

## Contents

1. What you need
2. Installation
3. Unpacking a file
4. Reading the output
5. Limitations
6. Troubleshooting

## 1. What you need

- Linux x86-64 and CPython 3.10–3.14 (FSD C-02).
- unblob **26.6.4** exactly (C-01). The package pins it; installing it into an
  environment with another unblob version replaces that version.
- For the installer formats, the external extractors on `PATH` (FSD §16.1):

| Command | Needed for | Version |
|---|---|---|
| `unshield` | InstallShield | 1.6.2 (Debian/Ubuntu package `unshield`) |
| `innoextract` | Inno Setup | upstream PR #210 at `376a13e7`, built from source. The packaged 1.9 fails on Inno Setup 6.4.3 and later |
| `sfextract` | Setup Factory | the fork `Ext745/sfextract` at `33399fae` (0.0.8 plus Setup Factory 10, SF 7.0.1/7.0.3, SF8 dependency-module and SF 9.2 fixes; upstream PR CybercentreCanada/sfextract#12) |
| `7z` | unblob's own CAB handler, when it recurses into Burn containers | as unblob's dependency list installs it |

UF2, Intel HEX, DfuSe, MCUboot, Zigbee OTA, GBL, `.cyacd`/`.cyacd2`,
single-file InstallShield packages and WiX/Burn need no external tool.
`.devcontainer/Dockerfile` builds all of the above and is the reference for
how to install them.

The Windows installer handlers sit beside the generic PE handler of unblob
PR #1255, which unblob 26.6.4 does not contain. Without #1255 the installers
in §7–§9 of the FSD are still claimed by these handlers, and NSIS installers
by this package's `nsis` handler, which carries #1255's NSIS code (FSD §13b).

## 2. Installation

The package is not on PyPI. Each release on GitHub
(https://github.com/Ext745/unblob-installer-handlers/releases) carries the
wheel and the sdist; use 0.1.2 or later (0.1.0 cannot extract Inno Setup or
InstallShield through the `unblob` command; 0.1.1 and earlier claim some
malformed InstallShield cabinets and drop volumes after a gap in a set, §6). Install a release's wheel,
or install from the source, into the same environment as unblob:

```sh
# from a checkout of this repository
git clone https://github.com/Ext745/unblob-installer-handlers
cd unblob-installer-handlers
pip install .

# or straight from GitHub, without a checkout
pip install git+https://github.com/Ext745/unblob-installer-handlers
```

To build a wheel to install elsewhere, run `pip install build==1.3.0` and
then `python -m build`, which writes the wheel to `dist/`.

When a `vX.Y.Z` tag is pushed, `.github/workflows/release.yml` builds the
wheel, runs the journey on it, and only if that passes publishes a GitHub
release with the wheel attached. Install a release's wheel with:

```sh
pip install unblob_installer_handlers-<version>-py3-none-any.whl
```

unblob discovers the handlers through the `unblob_v1` entry point (C-03); no
`-P` option is needed. Check that they loaded and that the extractors are
found:

```sh
unblob --show-external-dependencies
```

The listing names `unshield`, `innoextract` and `sfextract` with a ✓ when they
are on `PATH` (FR-PKG-05).

Without installing, point unblob at the package directory instead (FR-PKG-02):

```sh
unblob -P src/unblob_installers <file>
```

NSIS installers need no other plugin: the `nsis` handler extracts them with
`7z`. To use the generic PE handler of unblob PR #1255 alongside this
package, load it as a plugin too: `unblob -P /opt/pr1255 <file>`, where
`/opt/pr1255` holds the PR's `pe.py` as `.devcontainer/Dockerfile` installs
it; this package's handlers are asked first. See §5 on what changes once
#1255 is merged into unblob.

## 3. Unpacking a file

Run unblob as usual; the handlers have no options of their own (FSD §19):

```sh
unblob -e out/ --report report.json updater.exe
```

| Handler `NAME` | Claims |
|---|---|
| `uf2` | runs of 512-byte UF2 blocks |
| `ihex` | Intel HEX text, from a record's `:` to the end-of-file record, also when embedded in binary data |
| `dfuse` | ST DfuSe `.dfu` files, prefix to `UFD` suffix |
| `mcuboot` | MCUboot images (little-endian), header to end of the TLV area |
| `installshield` | a self-contained version 5 `data1.cab` |
| `installshield_set` | a directory holding a cabinet set (`data1.hdr` and/or `data1.cab` … `dataN.cab`), version 5 or 6 and later |
| `installshield_setup` | the `InstallShield\0` or `ISSetupStream\0` package after a single-file `setup.exe` stub, from its signature to the end of its last member |
| `inno` | a PE carrying Inno Setup 5.x–7.1 setup data |
| `setup_factory` | a PE carrying a Setup Factory 7–10 overlay |
| `wix_burn` | a PE with a `.wixburn` section |
| `cyacd` | a `.cyacd` header line (12 hex digits) followed by checksummed rows, through the last valid row |
| `cyacd2` | a `.cyacd2` header line (24 hex digits, file version `01`) followed by `@` and data lines, through the last valid data line |
| `nsis` | a PE whose NSIS firstheader sits at the first 512-byte boundary after the PE image |
| `gbl` | Silicon Labs GBL v3 (header tag `0x03A617EB`, version 3) through its end tag, plus `0xFF` padding to a 4-byte multiple |
| `zigbee_ota` | Zigbee OTA files (`0x0BEEF11E`, header version `0x0100`), header to the end of the total image size |

For a PE installer the chunk runs from `MZ` to the end of the overlay,
including an Authenticode certificate table; anything appended after it is
left to unblob (FR-PE-01/02).

## 4. Reading the output

Each chunk's output goes into `<chunk>_extract/` in unblob's extraction
directory, and unblob recurses into it.

**Firmware containers write one file per contiguous address region** — no
fill bytes, so a gap between regions is a gap between files. Addresses are
8 lowercase hex digits.

| Format | Output |
|---|---|
| UF2 | `<family>/0x<address>.bin` per region per family. `<family>` is the short name from `uf2families.json` (e.g. `RP2040`, `ESP32S3`), `no_family` for blocks without a family ID, `0x<familyid>` for an unknown one. "Not main flash" blocks are not written |
| Intel HEX | `0x<address>.bin` per region, addresses built from the `02`/`04` records |
| DfuSe | `target<alt>_<name>/0x<address>.bin` per element. `<name>` is the target name with every byte outside `[A-Za-z0-9._-]` replaced by `_`, or `unnamed` |
| MCUboot | `header.bin`, `image.bin` (ciphertext unchanged when encrypted), `tlv.bin` (protected TLVs, then TLVs) |
| InstallShield | the cabinet's files as `unshield x` writes them, e.g. `Firmware/app/firmware.bin` |
| Single-file InstallShield | each member under its stored name (`\` as the path separator), de-obfuscated and inflated, e.g. `Setup.ini`, `Product.msi`; unblob then unpacks the MSI and cabinets. A member that fails to inflate is written de-obfuscated, with an extraction problem naming it |
| Inno Setup | the installer's files as `innoextract -e` writes them, e.g. `app/firmware.bin` |
| Setup Factory | the installer's files as `sfextract` writes them, under folder variables such as `%AppFolder%/firmware.bin` |
| WiX/Burn | `u0.cab` (UX container) and `a0.cab`, `a1.cab` … (attached containers), byte-identical to the input ranges; unblob's CAB handler then unpacks each |

**MCUboot metadata** is in the report, not in a file: run with `--report` and
look for the `MCUbootImageReport` entry, which gives `version`
(`major.minor.revision+build`), `load_address`, `flags`, `signed` and
`encrypted`. `signed: true` means a signature TLV is present — the plugin
does not verify it (FSD §18).

## 5. Limitations

- InstallShield: a version 6+ `data1.cab` or `data1.hdr` on its own is not
  claimed (FR-ISC-06); unblob has to see the directory that holds the set,
  as it does when the set comes out of an installer or archive. A set with a
  missing volume (a gap in the `dataN.cab` numbers) or a `dataN.cab` without
  the `ISc(` signature is reported, not extracted (FR-ISC-09). InstallShield
  3 (`.Z`, `_sys1.cab`) is out of scope.
- Single-file InstallShield (`installshield_setup`): layout types 5 and later
  are not recognised. A member name that starts with `/`, carries a drive
  letter or a `..` component is not written; it is reported as an extraction
  problem (NFR-SEC-08).
- Setup Factory: installers declaring more than 1000 files (FR-SF-07), more
  than one dependency module or file (FR-SF-06), a script over 64 MiB
  (NFR-SEC-04) or an LZMA dictionary over 64 MiB (NFR-SEC-05) are declined,
  not unpacked.
- Inno Setup, Setup Factory, WiX/Burn with #1255: loaded as a plugin
  (`unblob -P`), #1255 leaves these installers to this package. In an unblob
  that has #1255 merged, its generic `pe` handler is asked first and claims
  the whole installer as a plain PE (FR-PE-03, FSD §4.1).
- MCUboot: big-endian images are not recognised; encrypted payloads are not
  decrypted.
- DfuSe: suffix-only DFU 1.1 files (no `DfuSe` prefix) are not recognised.
- Not handled at all: Wise, VISE, Gentee, UHARC, ISZ, Enigma VB, Motorola
  S-record, uImage, LittleFS/SPIFFS (FSD §4.4).

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ExtractorDependencyNotFoundReport` for `unshield`, `innoextract` or `sfextract`; the chunk is listed but has no files | The command is not on `PATH` (FR-COM-04) | Install it (§1), check with `unblob --show-external-dependencies` |
| Inno Setup chunk fails with an `ExtractError` from `innoextract` on a recent installer | The packaged innoextract 1.9 cannot read Inno Setup 6.4.3 and later | Build innoextract from PR #210 (§1) |
| Setup Factory 7.0.1/7.0.3, 8.1 or 9.2 installer fails in `sfextract` | Upstream sfextract 0.0.8 lacks the fixes | Install the pinned fork (§1) |
| Handlers missing from the run; only unblob's own handlers appear | Package installed in a different environment than the `unblob` on `PATH` | `pip install` into unblob's own venv, or use `-P` (§2) |
| UF2 or Intel HEX extraction fails naming two block or line numbers | The file writes different bytes to the same address (FR-UF2-08, FR-HEX-07) | The file is inconsistent; identical duplicate writes are accepted |
| Inno Setup or InstallShield: `UnknownError`, "No usable temporary directory" in the report | Version 0.1.0 under the `unblob` command: its sandbox blocked the handlers' scratch files (fixed in 0.1.1, FSD FR-COM-06) | Install 0.1.1 or later |
| An installer is unpacked only as a generic PE, or not at all | Not one of the supported installer types or versions (§5) | Check the version; for NSIS, check that `7z` is on PATH |
| A lone `data1.cab` from InstallShield 6+ is not unpacked | Only sets are claimed (FR-ISC-06) | Run unblob on the directory, or on an archive of it, that holds `data1.hdr` and the `.cab` volumes |
| InstallShield set: `ExtractionProblem` "InstallShield set has no dataN.cab volume" or "… lacks the ISc( signature", no files | A volume of the set is missing or is not a cabinet (FR-ISC-09); 0.1.1 and earlier extracted the volumes before the gap and dropped the rest without a report | Supply every volume `data1.cab` … `dataN.cab`, then run again |

---

**Contract:** [`../Functionality/unblob-installer-handlers-fsd.md`](../Functionality/unblob-installer-handlers-fsd.md) · **Build rules:** [`../Method/AI-Workflow.md`](../Method/AI-Workflow.md)
