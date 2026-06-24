#!/usr/bin/env bash
set -euo pipefail

export DOCKER_HOST="${DOCKER_HOST:-tcp://169.254.143.37:2376}"
export DOCKER_TLS_VERIFY="${DOCKER_TLS_VERIFY:-1}"
export DOCKER_CERT_PATH="${DOCKER_CERT_PATH:-/home/sunrise/.docker/nas-tudou}"

image="${1:-docker.1ms.run/library/ubuntu:22.04}"

echo "== docker version =="
docker version

echo "== image inspect =="
docker inspect "$image" | grep -E '"Architecture"|"Os"|"Id"|"RepoTags"'

echo "== run default =="
docker run --rm "$image" /bin/sh -lc '
  echo "uname=$(uname -m)"
  dpkg --print-architecture || true
  od -An -tx1 -N20 /bin/sh
'

echo "== run linux/amd64 =="
docker run --rm --platform linux/amd64 "$image" /bin/sh -lc '
  echo "uname=$(uname -m)"
  dpkg --print-architecture || true
  od -An -tx1 -N20 /bin/sh
'
