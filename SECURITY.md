# Security policy

## What counts as a vulnerability

The handlers parse files from vendors and from unknown sources, so every
input file is treated as hostile. The host, its Python environment and the
external tools (`unshield`, `innoextract`, `sfextract`, `7z`) are trusted.
A vulnerability is a file that makes a handler in this package:

- write outside unblob's extraction directory;
- use memory or disk out of proportion to the file, beyond the bounds the
  [user manual](docs/UserDocumentation/User-Manual.md#5-limitations) states
  (requirements NFR-SEC-01 to NFR-SEC-11);
- hang, or crash unblob in a way that hides other content of the file.

Not in scope, as stated in the specification's accepted risks:

- MCUboot, GBL and Zigbee OTA signatures are not verified, and encrypted
  payloads are not decrypted. `signed: true` means a signature is present.
- Defects inside the external tools. Report those to their projects; unblob's
  extraction timeout bounds them.
- A deflate bomb inside an InstallShield single-file package fills the
  extraction disk, as it would with unblob's own zlib and gzip handlers.
- The sum of many GBL tags, each under its cap.

## Supported versions

Only the latest release is supported; fixes ship as a new release.

| Version | Supported |
|---|---|
| 0.2.x | yes |
| 0.1.x and earlier | no |

## Reporting

Please report privately through GitHub: on this repository's **Security**
tab, choose **Report a vulnerability**. Include the unblob and package
versions, the command you ran, and a file that reproduces it, or the steps
to build one. Please do not open a public issue for a vulnerability.

You can expect an acknowledgement within a week. Once confirmed, the fix is
released with a note in the [changelog](CHANGELOG.md), crediting you unless
you ask otherwise. If the defect is in code this package carries from an
unblob pull request (NSIS from #1255, single-file InstallShield from #1707),
it is also reported to unblob.
