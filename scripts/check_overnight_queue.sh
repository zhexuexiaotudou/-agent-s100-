#!/usr/bin/env bash
set -euo pipefail

overnight_dir="${1:-/mnt/nas/openclaw/logs/overnight}"
report_dir="${2:-/mnt/nas/openclaw/reports/baseline-status}"

case "$overnight_dir" in
  /mnt/nas/openclaw/logs/overnight|/mnt/nas/openclaw/logs/overnight/*|/tmp/*) ;;
  *)
    echo "Refusing overnight dir outside approved paths: $overnight_dir" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/tmp/*) ;;
  *)
    echo "Refusing report dir outside approved paths: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
latest_queue_pid_file="$(find "$overnight_dir" -maxdepth 1 -type f -name 'overnight_queue_*.pid' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
latest_queue_log="$(find "$overnight_dir" -maxdepth 1 -type f -name 'overnight_queue_*.log' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/overnight_queue_status_$stamp.md"

pid="missing"
process_status="missing"
process_line=""
if [[ -n "$latest_queue_pid_file" && -f "$latest_queue_pid_file" ]]; then
  pid="$(tr -cd '0-9' < "$latest_queue_pid_file")"
  if [[ -n "$pid" ]] && process_line="$(ps -p "$pid" -o pid=,etime=,cmd= 2>/dev/null)"; then
    process_status="running"
  else
    process_status="not_running"
  fi
fi

{
  echo "# Overnight Queue Status"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- queue_pid_file: ${latest_queue_pid_file:-missing}"
  echo "- queue_log: ${latest_queue_log:-missing}"
  echo "- queue_pid: $pid"
  echo "- process_status: $process_status"
  if [[ -n "$process_line" ]]; then
    echo "- process_line: \`$(echo "$process_line" | sed 's/`//g')\`"
  fi
  echo
  echo "## Queue Log Tail"
  echo
  echo '```text'
  if [[ -n "$latest_queue_log" && -f "$latest_queue_log" ]]; then
    tail -80 "$latest_queue_log"
  else
    echo "missing"
  fi
  echo '```'
} > "$report"

echo "$report"
