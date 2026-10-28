#!/usr/bin/env bash
# Build the WiX/Burn fixture: an MSI installing the payload as firmware.bin,
# chained in a Burn bundle (WixStandardBootstrapperApplication).
# WiX 3.14.1 runs under Wine 10.0 with Wine Mono 9.4.0, in a throwaway
# container. Wine is a temporary build tool for fixtures only (user decision
# 2026-10-24, docs/Method/project/architecture.md).
# Usage: tests/fixtures/build-burn.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
WIX_URL=https://github.com/wixtoolset/wix3/releases/download/wix3141rtm/wix314-binaries.zip
WIX_SHA256=6ac824e1642d6f7277d0ed7ea09411a508f6116ba6fae0aa5f2c7daa2ff43d31
MONO_URL=https://dl.winehq.org/wine/wine-mono/9.4.0/wine-mono-9.4.0-x86.msi
MONO_SHA256=cf6173ae94b79e9de13d9a74cdb2560a886fc3d271f9489acb1cfdbd961cacb2
curl -fsSL -o "$WORK/wix.zip" "$WIX_URL" && echo "$WIX_SHA256  $WORK/wix.zip" | sha256sum -c --quiet -
curl -fsSL -o "$WORK/mono.msi" "$MONO_URL" && echo "$MONO_SHA256  $WORK/mono.msi" | sha256sum -c --quiet -
python3 "$HERE/payload.py" > "$WORK/firmware.bin"
cp "$HERE/burn-fixture.wxs" "$WORK/fixture.wxs"
cp "$HERE/burn-bundle.wxs" "$WORK/bundle.wxs"

docker run --rm -v "$WORK":/w ubuntu:26.04 bash -euc "
  trap 'chmod -R u+rw,go+r /w; chown -R $(id -u):$(id -g) /w' EXIT   # WiX under Wine leaves outputs mode 000
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    wine=10.0~repack-12ubuntu1 wine64=10.0~repack-12ubuntu1 unzip >/dev/null
  export WINEDEBUG=-all WINEPREFIX=/tmp/wp
  wineboot -i >/dev/null 2>&1
  wine msiexec /i /w/mono.msi /qn >/dev/null 2>&1
  mkdir -p /tmp/wix && (cd /tmp/wix && unzip -q /w/wix.zip)
  cd /w
  wine /tmp/wix/candle.exe -nologo fixture.wxs
  wine /tmp/wix/light.exe -nologo -sval fixture.wixobj -o fixture.msi
  wine /tmp/wix/candle.exe -nologo -ext WixBalExtension bundle.wxs
  wine /tmp/wix/light.exe -nologo -ext WixBalExtension bundle.wixobj -o standard.exe
"
OUT="$HERE/../integration/executable/wix_burn/__input__"
cp "$WORK/standard.exe" "$OUT/standard.exe"
(cd "$OUT" && sha256sum standard.exe && ls -l standard.exe | awk '{print $5, $9}')
