#!/usr/bin/env bash
set -euo pipefail

script="${DREAM7B_BPU_BATCH_QUEUE_RUNNER_SCRIPT:-/mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_bpu_batch_queue_runner.py}"

if [[ ! -f "$script" ]]; then
  echo "Missing Dream 7B BPU batch queue runner script: $script" >&2
  exit 4
fi

exec python3 "$script" "$@"
