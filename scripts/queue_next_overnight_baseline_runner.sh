#!/usr/bin/env bash
set -euo pipefail

hours="${1:-10}"
interval="${2:-1800}"
max_wait_hours="${3:-18}"
workspace="${OPENCLAW_WORKSPACE:-/root/.openclaw/workspace}"
overnight_dir="${OVERNIGHT_BASELINE_DIR:-/mnt/nas/openclaw/logs/overnight}"

case "$workspace" in
  /root/.openclaw/workspace|/root/.openclaw/workspace/*) ;;
  *)
    echo "Refusing workspace outside /root/.openclaw/workspace: $workspace" >&2
    exit 2
    ;;
esac

case "$overnight_dir" in
  /mnt/nas/openclaw/logs/overnight|/mnt/nas/openclaw/logs/overnight/*|/tmp/*) ;;
  *)
    echo "Refusing overnight dir outside approved paths: $overnight_dir" >&2
    exit 2
    ;;
esac

case "$hours" in
  ''|*[!0-9]*) echo "hours must be an integer" >&2; exit 2 ;;
esac

case "$interval" in
  ''|*[!0-9]*) echo "interval must be an integer" >&2; exit 2 ;;
esac

case "$max_wait_hours" in
  ''|*[!0-9]*) echo "max_wait_hours must be an integer" >&2; exit 2 ;;
esac

if (( hours < 1 || hours > 24 )); then
  echo "hours must be between 1 and 24" >&2
  exit 2
fi

if (( interval < 300 || interval > 7200 )); then
  echo "interval must be between 300 and 7200" >&2
  exit 2
fi

if (( max_wait_hours < 1 || max_wait_hours > 36 )); then
  echo "max_wait_hours must be between 1 and 36" >&2
  exit 2
fi

mkdir -p "$overnight_dir"
cd "$workspace"

latest_queue_pid_file="$(find "$overnight_dir" -maxdepth 1 -type f -name 'overnight_queue_*.pid' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
existing_queue_pid=""
if [[ -n "$latest_queue_pid_file" && -f "$latest_queue_pid_file" ]]; then
  existing_queue_pid="$(tr -cd '0-9' < "$latest_queue_pid_file")"
fi

if [[ -n "$existing_queue_pid" ]] && kill -0 "$existing_queue_pid" 2>/dev/null && [[ "${OVERNIGHT_QUEUE_ALLOW_DUPLICATE:-0}" != "1" ]]; then
  echo "An overnight queue is already running." >&2
  echo "EXISTING_QUEUE_PID:$existing_queue_pid"
  echo "EXISTING_QUEUE_PID_FILE:$latest_queue_pid_file"
  echo "Set OVERNIGHT_QUEUE_ALLOW_DUPLICATE=1 only if a duplicate queue is intentional." >&2
  exit 6
fi

latest_pid_file="$(find "$overnight_dir" -maxdepth 1 -type f -name 'overnight_baseline_*.pid' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
current_pid=""
if [[ -n "$latest_pid_file" && -f "$latest_pid_file" ]]; then
  current_pid="$(tr -cd '0-9' < "$latest_pid_file")"
fi

stamp="$(date +%Y%m%d-%H%M%S)"
queue_log="$overnight_dir/overnight_queue_$stamp.log"
queue_pid_file="$overnight_dir/overnight_queue_$stamp.pid"

launcher="$workspace/scripts/start_overnight_baseline_runner.sh"
if [[ ! -x "$launcher" ]]; then
  echo "Launcher missing or not executable: $launcher" >&2
  exit 4
fi

{
  echo "queued_at=$(date -Is)"
  echo "workspace=$workspace"
  echo "overnight_dir=$overnight_dir"
  echo "current_pid=${current_pid:-none}"
  echo "hours=$hours"
  echo "interval=$interval"
  echo "max_wait_hours=$max_wait_hours"
} > "$queue_log"

(
  set -euo pipefail
  echo "waiter_pid=${BASHPID:-$$}" >> "$queue_log"
  deadline=$(( $(date +%s) + max_wait_hours * 3600 ))
  if [[ -n "$current_pid" ]] && kill -0 "$current_pid" 2>/dev/null; then
    echo "waiting_for_pid=$current_pid" >> "$queue_log"
    while kill -0 "$current_pid" 2>/dev/null; do
      if (( $(date +%s) >= deadline )); then
        echo "status=timeout_waiting_for_pid" >> "$queue_log"
        exit 1
      fi
      sleep 60
    done
  else
    echo "no_running_current_pid=true" >> "$queue_log"
  fi

  echo "launching_at=$(date -Is)" >> "$queue_log"
  "$launcher" "$hours" "$interval" >> "$queue_log" 2>&1
  echo "status=launched" >> "$queue_log"
) </dev/null >/dev/null 2>&1 &

queue_pid="$!"
echo "$queue_pid" > "$queue_pid_file"
disown "$queue_pid" 2>/dev/null || true

echo "QUEUE_PID:$queue_pid"
echo "QUEUE_PID_FILE:$queue_pid_file"
echo "QUEUE_LOG:$queue_log"
echo "CURRENT_PID:${current_pid:-none}"
