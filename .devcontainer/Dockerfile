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

# sfextract (FSD C-04) next to unblob, so the handlers find it on PATH.
RUN python3 -m venv /opt/tools-venv \
 && /opt/tools-venv/bin/pip install --no-cache-dir 'unblob==26.6.4' 'sfextract==0.0.8'

# The image's uid 1000 is "ubuntu"; the runner refuses to run as root.
WORKDIR /home/ubuntu/actions-runner
RUN curl -fsSL -o runner.tgz \
      https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz \
 && echo "${RUNNER_SHA256}  runner.tgz" | sha256sum -c - \
 && tar xzf runner.tgz && rm runner.tgz \
 && ./bin/installdependencies.sh \
 && chown -R ubuntu:ubuntu /home/ubuntu/actions-runner

COPY --from=innoextract /usr/local/bin/innoextract /usr/local/bin/innoextract
COPY runner-loop.sh /usr/local/bin/runner-loop.sh
USER ubuntu
ENV PATH=/opt/tools-venv/bin:$PATH
CMD ["/usr/local/bin/runner-loop.sh"]
