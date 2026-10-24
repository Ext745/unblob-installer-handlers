# The project's one container: Python with unblob 26.6.4, the external
# extractors (FSD §16.1), and the GitHub Actions runner every CI job runs on.
# Ubuntu 26.04 matches the bench PC, whose firmware-re venv runs Python 3.14.
FROM ubuntu:26.04

ARG RUNNER_VERSION=2.337.0
ARG RUNNER_SHA256=70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613

# Extractors: unblob's list (as in the harness's firmware-re component) plus
# this project's unshield 1.6.2 and innoextract 1.9 (FSD C-04). nodejs is for pyright.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      python3 python3-venv git curl jq ca-certificates nodejs \
      7zip 7zip-standalone android-sdk-libsparse-utils cabextract cpio \
      device-tree-compiler e2fsprogs erofs-utils lz4 lziprecover lzop partclone \
      sleuthkit srecord unar unyaffs unzip zstd libxxhash0 \
      unshield=1.6.2-2 innoextract=1.9-3 \
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

COPY runner-loop.sh /usr/local/bin/runner-loop.sh
USER ubuntu
ENV PATH=/opt/tools-venv/bin:$PATH
CMD ["/usr/local/bin/runner-loop.sh"]
