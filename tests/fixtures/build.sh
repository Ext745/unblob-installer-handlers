#!/usr/bin/env bash
# Build the fixture sources (debugging agenda: fixture-sources) inside the
# devcontainer image, then prove each one with its oracle (FSD §16.1).
# Usage: tests/fixtures/build.sh   -> writes tests/integration/<category>/<name>/__input__/*
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
docker run --rm --network none -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$HERE/..":/t unblob-installer-handlers-dev bash -euc '
cd /t/integration
mkdir -p archive/{uf2,ihex,dfuse,mcuboot,installshield,installshield_setup,zigbee_ota,gbl,cyacd,cyacd2}/__input__ executable/{nsis,installshield_plain}/__input__
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
python3 ../fixtures/installshield_cab.py /tmp/firmware.bin archive/installshield/__input__/set.tar --set
mkdir -p /tmp/isset && tar -xf archive/installshield/__input__/set.tar -C /tmp/isset
unshield -d /tmp/isset-out x /tmp/isset/set/data1.hdr >/dev/null && cmp /tmp/firmware.bin /tmp/isset-out/Firmware/app/firmware.bin && echo "installshield: the data1.hdr + data1.cab set extracts firmware.bin identical"

# NSIS: makensis 3.10; build time and file mtime pinned so the output is reproducible
mkdir -p /tmp/nsisbuild && cp ../fixtures/standard.nsi /tmp/nsisbuild/ && cp /tmp/firmware.bin /tmp/nsisbuild/firmware.bin
touch -d @1700000000 /tmp/nsisbuild/firmware.bin
(cd /tmp/nsisbuild && SOURCE_DATE_EPOCH=1700000000 makensis -V2 standard.nsi >/dev/null) && cp /tmp/nsisbuild/standard.exe executable/nsis/__input__/standard.exe
7z e -y -bd -o/tmp/nsisout executable/nsis/__input__/standard.exe firmware.bin >/dev/null && cmp /tmp/firmware.bin /tmp/nsisout/firmware.bin && echo "nsis: payload extracted identical"
# Zigbee OTA (FSD §13c): tests/zigbee_ota_image.py, written from the FSD; the
# oracle is an independent read of the sub-element holding the payload
python3 /t/zigbee_ota_image.py archive/zigbee_ota/__input__/standard.ota
python3 -c "import sys,struct; d=open(sys.argv[1],\"rb\").read(); p=open(\"/tmp/firmware.bin\",\"rb\").read(); t,l=struct.unpack_from(\"<HI\",d,56); sys.exit(0 if (t,d[62:62+l])==(0,p) else 1)" archive/zigbee_ota/__input__/standard.ota && echo "zigbee_ota: upgrade image identical to the payload"

# GBL v3 (FSD §13d): built with pygbl (oracle, /opt/tools-venv); the script
# checks that pygbl parses each file back and the program data is the payload
/opt/tools-venv/bin/python -I /t/gbl_image.py /tmp/firmware.bin archive/gbl/__input__

# .cyacd / .cyacd2 (FSD §13e): tests/cyacd_image.py, written from the FSD
mkdir -p /tmp/cy && python3 /t/cyacd_image.py /tmp/firmware.bin /tmp/cy
cp /tmp/cy/standard.cyacd archive/cyacd/__input__/ && cp /tmp/cy/standard.cyacd2 /tmp/cy/encrypted.cyacd2 archive/cyacd2/__input__/
python3 -c "import binascii,sys; p=open(\"/tmp/firmware.bin\",\"rb\").read(); rows=[binascii.unhexlify(l[1:]) for l in open(sys.argv[1],\"rb\").read().split(b\"\\r\\n\") if l.startswith(b\":\")]; sys.exit(0 if all(sum(r)&0xFF==0 for r in rows) and b\"\".join(r[5:-1] for r in rows)==p[:768] else 1)" archive/cyacd/__input__/standard.cyacd && echo "cyacd: row checksums valid, rows equal the payload"

# InstallShield single-file packages (FSD §13a): tests/installshield_setup_image.py, written from §13a.1
python3 /t/installshield_setup_image.py /tmp/firmware.bin archive/installshield_setup/__input__
python3 /t/installshield_plain_image.py /tmp/firmware.bin executable/installshield_plain/__input__
'
cd "$HERE/../integration" && ls -l */*/__input__/*.{uf2,hex,dfu,bin,cab,tar,ota,gbl,cyacd,cyacd2,pftw} executable/nsis/__input__/standard.exe executable/installshield_plain/__input__/*.exe | awk '{print $5, $9}' && sha256sum */*/__input__/*.{uf2,hex,dfu,bin,cab,tar,ota,gbl,cyacd,cyacd2,pftw} executable/nsis/__input__/standard.exe executable/installshield_plain/__input__/*.exe
