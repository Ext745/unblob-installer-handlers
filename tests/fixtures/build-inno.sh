#!/usr/bin/env bash
# Build the Inno Setup fixtures (FSD FR-INNO-03: one per Inno version).
# Wine runs Inno's own compiler (ISCC.exe) only to produce these test inputs.
# It is a temporary build tool for this script alone (user decision
# 2026-10-24, docs/Method/project/architecture.md), never part of the plugin
# or its tests.
# Usage: tests/fixtures/build-inno.sh <dir with innosetup-<version>*.exe>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(realpath "$1")
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
python3 "$HERE/payload.py" > "$WORK/firmware.bin"
cp "$HERE/standard.iss" "$WORK/"

# 1. Extract each Inno Setup release's compiler with innoextract (FSD §16.1).
docker run --rm --network none -u "$(id -u):$(id -g)" -v "$SRC":/s:ro -v "$WORK":/w \
  unblob-installer-handlers-dev bash -euc '
  for f in /s/innosetup-*.exe; do
    v=$(basename "$f" .exe); v=${v#innosetup-}; v=${v%-x86}
    innoextract -e -s -d "/w/iscc-$v" "$f" >/dev/null
  done'

# 2. Compile with each version's ISCC.exe under Wine, in a throwaway container.
docker run --rm -v "$WORK":/w ubuntu:26.04 bash -euc "
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    wine=10.0~repack-12ubuntu1 wine64=10.0~repack-12ubuntu1 >/dev/null
  export WINEDEBUG=-all WINEPREFIX=/tmp/wp
  cd /w
  for d in iscc-*/; do
    v=\${d%/}; v=\${v#iscc-}
    iscc=\$(find \"\$d\" -iname ISCC.exe | head -1)
    wine \"\$iscc\" /Q /DOutName=standard-\$v standard.iss >/dev/null 2>&1 || { echo \"ISCC \$v failed\"; exit 1; }
  done
  chown -R $(id -u):$(id -g) /w
"

# 3. Prove each with innoextract: it must yield firmware.bin identical to the payload.
docker run --rm --network none -u "$(id -u):$(id -g)" -v "$WORK":/w \
  unblob-installer-handlers-dev bash -euc '
  cd /w/out
  for f in standard-*.exe; do
    innoextract -e -s -d "/tmp/x-$f" "$f" >/dev/null 2>&1
    cmp /w/firmware.bin "$(find "/tmp/x-$f" -name firmware.bin)"
    echo "$f: payload extracted identical ($(innoextract -i "$f" 2>&1 | grep -o "setup data version [0-9.]*"))"
  done'

mkdir -p "$HERE/../integration/executable/inno/__input__"
OUT="$HERE/../integration/executable/inno/__input__"
rm -f "$OUT"/standard-*.exe
cp "$WORK"/out/standard-*.exe "$OUT/"
(cd "$OUT" && sha256sum *.exe && ls -l *.exe | awk '{print $5, $9}')
