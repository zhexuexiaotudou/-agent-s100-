#!/usr/bin/env bash
set -euo pipefail

export DOCKER_HOST="${DOCKER_HOST:-tcp://169.254.143.37:2376}"
export DOCKER_TLS_VERIFY="${DOCKER_TLS_VERIFY:-1}"
export DOCKER_CERT_PATH="${DOCKER_CERT_PATH:-/home/sunrise/.docker/nas-tudou}"

image="${1:-docker.1ms.run/library/ubuntu:22.04}"
workspace_host="${NAS_WORKSPACE_HOST_PATH:-/share/OpenClawWorkspace}"
workspace="${WORKSPACE:-/mnt/nas/openclaw}"

docker run --rm --platform linux/amd64 \
  -v "$workspace_host:$workspace" \
  -e WORKSPACE="$workspace" \
  "$image" \
  /bin/bash -lc '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends qemu-user-static file python3.10
    echo "native:"
    file /bin/bash "$WORKSPACE/tmp/dream-s100-oellm-venv/bin/python3.10"
    "$WORKSPACE/tmp/dream-s100-oellm-venv/bin/python3.10" - <<PY
import platform
print(platform.machine())
PY
    echo "qemu:"
    QEMU_CPU=max /usr/bin/qemu-x86_64-static "$WORKSPACE/tmp/dream-s100-oellm-venv/bin/python3.10" - <<PY
import platform
print(platform.machine())
PY
    QEMU_CPU=max /usr/bin/qemu-x86_64-static "$WORKSPACE/tmp/dream-s100-oellm-venv/bin/python3.10" "$WORKSPACE/tmp/dream-s100-oellm-venv/bin/oellm_build" --help | head -12
  '
