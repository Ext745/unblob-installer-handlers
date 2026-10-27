#!/usr/bin/env bash
# Build the fixture sources (debugging agenda: fixture-sources) inside the
# devcontainer image, then prove each one with its oracle (FSD §16.1).
# Usage: tests/fixtures/build.sh   -> writes tests/fixtures/<format>/standard.*
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
docker run --rm --network none -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$HERE":/f unblob-installer-handlers-dev bash -euc '
cd /f
mkdir -p uf2 ihex dfuse mcuboot nsis
python3 payload.py > /tmp/firmware.bin

# UF2: RP2040 family at 0x10000000
python3 /opt/oracles/uf2conv.py -c -b 0x10000000 -f 0xe48bff56 -o uf2/standard.uf2 /tmp/firmware.bin >/dev/null
python3 /opt/oracles/uf2conv.py -c -o /tmp/uf2.bin uf2/standard.uf2 >/dev/null 2>&1
cmp /tmp/firmware.bin /tmp/uf2.bin && echo "uf2: round trip identical"

# Intel HEX at 0x08000000
avr-objcopy -I binary -O ihex --change-addresses 0x08000000 /tmp/firmware.bin ihex/standard.hex
avr-objcopy -I ihex -O binary ihex/standard.hex /tmp/hex.bin
cmp /tmp/firmware.bin /tmp/hex.bin && echo "ihex: round trip identical"

# DfuSe: one target, one element at 0x08000000, ST VID/PID
python3 /opt/oracles/dfuse-pack.py -b 0x08000000:/tmp/firmware.bin -D 0x0483:0xdf11 dfuse/standard.dfu >/dev/null
dfu-suffix -c dfuse/standard.dfu >/dev/null && echo "dfuse: suffix and CRC valid"

# MCUboot: unsigned (hash TLV only), version 1.2.3+4
imgtool sign --header-size 0x20 --pad-header --align 4 --version 1.2.3+4 --slot-size 0x10000 /tmp/firmware.bin mcuboot/standard.bin >/dev/null
imgtool verify mcuboot/standard.bin | tail -1
python3 -c "import sys; d=open(sys.argv[1],\"rb\").read(); sys.exit(0 if d[0x20:0x20+4096]==open(\"/tmp/firmware.bin\",\"rb\").read() else 1)" mcuboot/standard.bin && echo "mcuboot: image bytes identical"

# MCUboot, encrypted (FR-MCB-08): AES-128 with a throwaway X25519 key. The AES key
# is random per build, so this file is not reproducible; the committed bytes are
# the fixture.
imgtool keygen -k /tmp/enc.pem -t x25519
imgtool sign --header-size 0x20 --pad-header --align 4 --version 1.2.3+4 --slot-size 0x10000 -E /tmp/enc.pem /tmp/firmware.bin mcuboot/encrypted.bin >/dev/null
imgtool dumpinfo mcuboot/encrypted.bin | grep -q "flags: *ENCRYPTED_AES128" && echo "mcuboot: encrypted image flagged ENCRYPTED_AES128"
python3 -c "import sys; d=open(sys.argv[1],\"rb\").read(); sys.exit(1 if d[0x20:0x20+4096]==open(\"/tmp/firmware.bin\",\"rb\").read() else 0)" mcuboot/encrypted.bin && echo "mcuboot: encrypted image bytes differ from the payload"

# NSIS: makensis 3.10; build time and file mtime pinned so the output is reproducible
mkdir -p /tmp/nsisbuild && cp standard.nsi /tmp/nsisbuild/ && cp /tmp/firmware.bin /tmp/nsisbuild/firmware.bin
touch -d @1700000000 /tmp/nsisbuild/firmware.bin
(cd /tmp/nsisbuild && SOURCE_DATE_EPOCH=1700000000 makensis -V2 standard.nsi >/dev/null) && cp /tmp/nsisbuild/standard.exe nsis/standard.exe
7z e -y -bd -o/tmp/nsisout nsis/standard.exe firmware.bin >/dev/null && cmp /tmp/firmware.bin /tmp/nsisout/firmware.bin && echo "nsis: payload extracted identical"
'
cd "$HERE" && sha256sum */standard.* mcuboot/encrypted.bin && ls -l */standard.* mcuboot/encrypted.bin | awk '{print $5, $9}'
