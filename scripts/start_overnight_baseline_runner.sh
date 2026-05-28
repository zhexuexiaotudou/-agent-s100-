#!/usr/bin/env bash
set -euo pipefail

hours="${1:-10}"
interval="${2:-1800}"
workspace="/root/.openclaw/workspace"
out_dir="/mnt/nas/openclaw/logs/overnight"

case "$hours" in
  ''|*[!0-9]*) echo "hours must be an integer" >&2; exit 2 ;;
esac

case "$interval" in
  ''|*[!0-9]*) echo "interval must be an integer" >&2; exit 2 ;;
esac

if (( hours < 1 || hours > 24 )); then
  echo "hours must be between 1 and 24" >&2
  exit 2
fi

if (( interval < 300 || interval > 7200 )); then
  echo "interval must be between 300 and 7200" >&2
  exit 2
fi

mkdir -p "$out_dir"
cd "$workspace"

stamp="$(date +%Y%m%d-%H%M%S)"
launch_log="$out_dir/overnight_launch_$stamp.out"

nohup env \
  OVERNIGHT_BASELINE_HOURS="$hours" \
  OVERNIGHT_BASELINE_INTERVAL_SECONDS="$interval" \
  scripts/overnight_baseline_runner.sh > "$launch_log" 2>&1 &

pid="$!"
sleep 2

if ! kill -0 "$pid" 2>/dev/null; then
  echo "runner failed to stay alive" >&2
  sed -n '1,120p' "$launch_log" >&2 || true
  exit 1
fi

echo "PID:$pid"
echo "LAUNCH_LOG:$launch_log"
echo "OUT_DIR:$out_dir"
