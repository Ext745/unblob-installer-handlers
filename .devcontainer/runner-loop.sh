#!/usr/bin/env bash
# Ephemeral self-hosted runner in a restart loop: register, take one job,
# deregister, repeat. Needs GH_RUNNER_PAT (fine-grained, this repo only,
# Administration: read/write) and GH_REPO (owner/name) from .env.
set -u
cd /home/ubuntu/actions-runner
: "${GH_RUNNER_PAT:?set GH_RUNNER_PAT in .devcontainer/.env}"
: "${GH_REPO:?set GH_REPO in .devcontainer/.env}"
while true; do
    token=$(  # scrub:allow command substitution, no value here
        curl -fsS -X POST -H "Authorization: Bearer $GH_RUNNER_PAT" \
              -H "Accept: application/vnd.github+json" \
              "https://api.github.com/repos/$GH_REPO/actions/runners/registration-token" | jq -r .token)
    if [ -z "$token" ] || [ "$token" = null ]; then
        echo "runner-loop: no registration token (PAT expired or lacks Administration?); retrying in 60 s" >&2
        sleep 60; continue
    fi
    # An ephemeral runner is deleted on the server after its job, but its
    # local registration stays; config.sh then refuses to register again.
    rm -f .runner .credentials .credentials_rsaparams
    ./config.sh --unattended --ephemeral --replace \
        --url "https://github.com/$GH_REPO" --token "$token" \
        --name "unblob-installer-handlers-$(hostname)" --labels testbench --work _work
    ./run.sh
    sleep 5
done
