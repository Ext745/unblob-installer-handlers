# The project's one container: Python with unblob 26.6.4, the external
# extractors (FSD §16.1), and the GitHub Actions runner every CI job runs on.
# Ubuntu 26.04 matches the bench PC, whose firmware-re venv runs Python 3.14.
# innoextract from upstream PR #210 at a pinned commit (FSD §16.1, C-04): the
# 1.9 package and master fail on Inno Setup >= 6.4.3; PR #210 reads 6.1-7.1.
FROM ubuntu:26.04 AS innoextract
ARG INNOEXTRACT_REV=376a13e7c41cc5528b6088d0dd16ec1b323a8d37
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates git cmake g++ make libboost-iostreams-dev libboost-filesystem-dev \
      libboost-date-time-dev libboost-system-dev libboost-program-options-dev \
      liblzma-dev zlib1g-dev libbz2-dev \
 && git clone https://github.com/dscharrer/innoextract /src \
 && git -C /src fetch origin pull/210/head \
 && git -C /src checkout "$INNOEXTRACT_REV" \
 # Boost >= 1.89 has no boost_system CMake package (it is header-only now).
 && sed -i '/^find_package(Boost REQUIRED COMPONENTS/,/^)/{/^\tsystem$/d}' /src/CMakeLists.txt \
 && cmake -S /src -B /build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local \
 && cmake --build /build -j"$(nproc)" && cmake --install /build

FROM ubuntu:26.04

ARG RUNNER_VERSION=2.337.0
ARG RUNNER_SHA256=70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613

# Extractors: unblob's list (as in the harness's firmware-re component) plus
# this project's unshield 1.6.2 (FSD C-04). nodejs is for pyright.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      python3 python3-venv git curl jq ca-certificates nodejs \
      7zip 7zip-standalone android-sdk-libsparse-utils cabextract cpio \
      device-tree-compiler e2fsprogs erofs-utils lz4 lziprecover lzop partclone \
      sleuthkit srecord unar unyaffs unzip zstd libxxhash0 \
      unshield=1.6.2-2 \
      libboost-iostreams1.90.0 libboost-filesystem1.90.0 libboost-program-options1.90.0 liblzma5 \
 && rm -rf /var/lib/apt/lists/*

# sfextract (FSD C-04) next to unblob, so the handlers find it on PATH: 0.0.8
# plus Setup Factory 10 support, pinned by commit on this project's fork until
# an upstream release contains it (FSD §16.1, C-11).
# imgtool and intelhex are test oracles (FSD §16.1), never called by a handler.
ARG SFEXTRACT_REV=ca5c3a65485f6c6c3731f81207e613e17a8f29f4
RUN python3 -m venv /opt/tools-venv \
 && /opt/tools-venv/bin/pip install --no-cache-dir 'unblob==26.6.4' \
      "sfextract @ git+https://github.com/Ext745/sfextract@${SFEXTRACT_REV}" \
      'imgtool==2.5.0' 'intelhex==2.3.0'

# CPython 3.10 for C-02's lower bound: Ubuntu 26.04 packages no 3.10, so a
# pinned python-build-standalone build. TC-CON-02 builds a venv from it and
# runs the unit and integration suites; the wheelhouse makes that install
# offline. Never on PATH: handlers and the 3.14 suite do not see it.
ARG PY310_BUILD=20261009
ARG PY310_SHA256=1780de9ddda04e956d2a4a0ad09b7f5667d92f4f12cd0881ec939de5d542903f
RUN curl -fsSL -o /tmp/py310.tgz \
      "https://github.com/astral-sh/python-build-standalone/releases/download/${PY310_BUILD}/cpython-3.10.22%2B${PY310_BUILD}-x86_64-unknown-linux-gnu-install_only.tar.gz" \
 && echo "${PY310_SHA256}  /tmp/py310.tgz" | sha256sum -c - \
 && mkdir -p /opt/python3.10 && tar xzf /tmp/py310.tgz -C /opt/python3.10 --strip-components=1 \
 && rm /tmp/py310.tgz \
 && /opt/python3.10/bin/python3 -m pip wheel -q --no-cache-dir -w /opt/wheels-py310 \
      'unblob==26.6.4' 'pytest==8.4.2' 'ruff==0.15.14' 'pyright==1.1.410' 'hatchling==1.27.0' 'editables==0.5'

# Oracles for tests (FSD §16.1): dfu-util and avr-objcopy from Ubuntu (and
# makensis, which builds the NSIS fixture),
# uf2conv.py with the uf2families.json this project vendors (FSD D-3), and
# dfuse-pack.py from the dfu-util 0.11 release.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      dfu-util=0.11-3build1 binutils-avr=2.43.50.20250108-1build1 nsis=3.10-2ubuntu2 \
 && rm -rf /var/lib/apt/lists/*
ARG UF2_REV=90e9741f217f5a40c98ba74d663e408041037578
ARG DFU_UTIL_SHA256=b4b53ba21a82ef7e3d4c47df2952adf5fa494f499b6b0b57c58c5d04ae8ff19e
RUN mkdir -p /opt/oracles \
 && curl -fsSL -o /opt/oracles/uf2conv.py https://raw.githubusercontent.com/microsoft/uf2/${UF2_REV}/utils/uf2conv.py \
 && curl -fsSL -o /opt/oracles/uf2families.json https://raw.githubusercontent.com/microsoft/uf2/${UF2_REV}/utils/uf2families.json \
 && curl -fsSL -o /tmp/dfu-util.tgz https://dfu-util.sourceforge.net/releases/dfu-util-0.11.tar.gz \
 && echo "${DFU_UTIL_SHA256}  /tmp/dfu-util.tgz" | sha256sum -c - \
 && tar xzf /tmp/dfu-util.tgz -C /opt/oracles --strip-components=1 dfu-util-0.11/dfuse-pack.py \
 && rm /tmp/dfu-util.tgz

# The image's uid 1000 is "ubuntu"; the runner refuses to run as root.
WORKDIR /home/ubuntu/actions-runner
RUN curl -fsSL -o runner.tgz \
      https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz \
 && echo "${RUNNER_SHA256}  runner.tgz" | sha256sum -c - \
 && tar xzf runner.tgz && rm runner.tgz \
 && ./bin/installdependencies.sh \
 && chown -R ubuntu:ubuntu /home/ubuntu/actions-runner

COPY --from=innoextract /usr/local/bin/innoextract /usr/local/bin/innoextract

# PR #1255's PE/NSIS handler (FSD §15, D-1) at a pinned head, as a plugin
# package for tests: unblob -P /opt/pr1255. Its only code change upstream is
# this module plus one registration line.
ARG PR1255_REV=6e799adc62b548012faa912b13eb0eed455fb800
ARG PR1255_PE_SHA256=afd8a7a76fa99347baf1bb67252f32832aa9f93b7a01f233d8e96c037fd98425
COPY pr1255/__init__.py /opt/pr1255/unblob_pr1255/__init__.py
RUN curl -fsSL -o /opt/pr1255/unblob_pr1255/pe.py \
      https://raw.githubusercontent.com/onekey-sec/unblob/${PR1255_REV}/python/unblob/handlers/executable/pe.py \
 && echo "${PR1255_PE_SHA256}  /opt/pr1255/unblob_pr1255/pe.py" | sha256sum -c - \
 && sed -i 's/^from \.\.\.\(file_utils\|models\|extractors\|report\)/from unblob.\1/; s/^from \.\.\./from unblob./' /opt/pr1255/unblob_pr1255/pe.py
COPY runner-loop.sh /usr/local/bin/runner-loop.sh
USER ubuntu
ENV PATH=/opt/tools-venv/bin:$PATH
CMD ["/usr/local/bin/runner-loop.sh"]
