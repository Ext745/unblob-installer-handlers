#!/usr/bin/env bash
# Build the fixture sources (debugging agenda: fixture-sources) inside the
# devcontainer image, then prove each one with its oracle (FSD §16.1).
# Usage: tests/fixtures/build.sh   -> writes tests/integration/<category>/<name>/__input__/*
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
docker run --rm --network none -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$HERE/..":/t unblob-installer-handlers-dev bash -euc '
cd /t/integration
mkdir -p archive/{uf2,ihex,dfuse,mcuboot,installshield}/__input__ executable/nsis/__input__
python3 ../fixtures/payload.py > /tmp/firmware.bin

# UF2: RP2040 family at 0x10000000
python3 /opt/oracles/uf2conv.py -c -b 0x10000000 -f 0xe48bff56 -o archive/uf2/__input__/standard.uf2 /tmp/firmware.bin >/dev/null
python3 /opt/oracles/uf2conv.py -c -o /tmp/uf2.bin archive/uf2/__input__/standard.uf2 >/dev/null 2>&1
cmp /tmp/firmware.bin /tmp/uf2.bin && echo "uf2: round trip identical"

# Intel HEX at 0x08000000
avr-objcopy -I binary -O ihex --change-addresses 0x08000000 /tmp/firmware.bin archive/ihex/__input__/standard.hex
avr-objcopy -I ihex -O binary archive/ihex/__input__/standard.hex /tmp/hex.bin
cmp /tmp/firmware.bin /tmp/hex.bin && echo "ihex: round trip identical"

# DfuSe: one target, one element at 0x08000000, ST VID/PID
python3 /opt/oracles/dfuse-pack.py -b 0x08000000:/tmp/firmware.bin -D 0x0483:0xdf11 archive/dfuse/__input__/standard.dfu >/dev/null
dfu-suffix -c archive/dfuse/__input__/standard.dfu >/dev/null && echo "dfuse: suffix and CRC valid"

# MCUboot: unsigned (hash TLV only), version 1.2.3+4
imgtool sign --header-size 0x20 --pad-header --align 4 --version 1.2.3+4 --slot-size 0x10000 /tmp/firmware.bin archive/mcuboot/__input__/standard.bin >/dev/null
imgtool verify archive/mcuboot/__input__/standard.bin | tail -1
python3 -c "import sys; d=open(sys.argv[1],\"rb\").read(); sys.exit(0 if d[0x20:0x20+4096]==open(\"/tmp/firmware.bin\",\"rb\").read() else 1)" archive/mcuboot/__input__/standard.bin && echo "mcuboot: image bytes identical"

# MCUboot, encrypted (FR-MCB-08): AES-128 with a throwaway X25519 key. The AES key
# is random per build, so this file is not reproducible; the committed bytes are
# the fixture.
imgtool keygen -k /tmp/enc.pem -t x25519
imgtool sign --header-size 0x20 --pad-header --align 4 --version 1.2.3+4 --slot-size 0x10000 -E /tmp/enc.pem /tmp/firmware.bin archive/mcuboot/__input__/encrypted.bin >/dev/null
imgtool dumpinfo archive/mcuboot/__input__/encrypted.bin | grep -q "flags: *ENCRYPTED_AES128" && echo "mcuboot: encrypted image flagged ENCRYPTED_AES128"
python3 -c "import sys; d=open(sys.argv[1],\"rb\").read(); sys.exit(1 if d[0x20:0x20+4096]==open(\"/tmp/firmware.bin\",\"rb\").read() else 0)" archive/mcuboot/__input__/encrypted.bin && echo "mcuboot: encrypted image bytes differ from the payload"

# MCUboot with a protected TLV area (FR-MCB-03): the security counter goes there
imgtool sign --header-size 0x20 --pad-header --align 4 --version 1.2.3+4 --slot-size 0x10000 --security-counter 7 /tmp/firmware.bin archive/mcuboot/__input__/protected.bin >/dev/null
imgtool dumpinfo archive/mcuboot/__input__/protected.bin | grep -q "Protected TLV area" && echo "mcuboot: protected TLV area present"

# InstallShield: a version 5 cabinet written by installshield_cab.py (layout as
# unshield 1.6.2 reads it), checked by unshield itself
python3 ../fixtures/installshield_cab.py /tmp/firmware.bin archive/installshield/__input__/standard.cab
cp archive/installshield/__input__/standard.cab /tmp/data1.cab
unshield -d /tmp/isout x /tmp/data1.cab >/dev/null && cmp /tmp/firmware.bin /tmp/isout/Firmware/app/firmware.bin && echo "installshield: unshield extracts firmware.bin identical"

# NSIS: makensis 3.10; build time and file mtime pinned so the output is reproducible
mkdir -p /tmp/nsisbuild && cp ../fixtures/standard.nsi /tmp/nsisbuild/ && cp /tmp/firmware.bin /tmp/nsisbuild/firmware.bin
touch -d @1700000000 /tmp/nsisbuild/firmware.bin
(cd /tmp/nsisbuild && SOURCE_DATE_EPOCH=1700000000 makensis -V2 standard.nsi >/dev/null) && cp /tmp/nsisbuild/standard.exe executable/nsis/__input__/standard.exe
7z e -y -bd -o/tmp/nsisout executable/nsis/__input__/standard.exe firmware.bin >/dev/null && cmp /tmp/firmware.bin /tmp/nsisout/firmware.bin && echo "nsis: payload extracted identical"
'
cd "$HERE/../integration" && ls -l */*/__input__/*.{uf2,hex,dfu,bin,cab} executable/nsis/__input__/standard.exe | awk '{print $5, $9}' && sha256sum */*/__input__/*.{uf2,hex,dfu,bin,cab} executable/nsis/__input__/standard.exe
