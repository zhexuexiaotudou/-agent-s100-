#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pid_file="$repo_root/tmp/stage2_sidecar_mock.pid"
log_file="$repo_root/tmp/stage2_sidecar_mock.log"
port="${STAGE2_SIDECAR_PORT:-19080}"

if [[ "$port" == "8765" || "$port" == "18080" || "$port" == "18888" || "$port" == "18889" ]]; then
  echo "refusing protected port $port" >&2
  exit 2
fi

if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
  echo "already_running pid=$(cat "$pid_file")"
  exit 0
fi

if command -v py >/dev/null 2>&1; then
  py -3 "$repo_root/stage2_sidecar/mock_server.py" --port "$port" >"$log_file" 2>&1 &
elif command -v python3 >/dev/null 2>&1; then
  python3 "$repo_root/stage2_sidecar/mock_server.py" --port "$port" >"$log_file" 2>&1 &
else
  python "$repo_root/stage2_sidecar/mock_server.py" --port "$port" >"$log_file" 2>&1 &
fi
echo "$!" > "$pid_file"
echo "started pid=$(cat "$pid_file") port=$port log=$log_file"
