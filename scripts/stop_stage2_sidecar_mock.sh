#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pid_file="$repo_root/tmp/stage2_sidecar_mock.pid"

if [[ ! -f "$pid_file" ]]; then
  echo "stopped=true reason=no_pid_file"
  exit 0
fi
pid="$(cat "$pid_file")"
if kill -0 "$pid" 2>/dev/null; then
  kill "$pid" 2>/dev/null || true
  sleep 0.5
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
fi
rm -f "$pid_file"
echo "stopped=true pid=$pid"
