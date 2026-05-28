#!/usr/bin/env bash
set -euo pipefail

overnight_dir="${1:-/mnt/nas/openclaw/logs/overnight}"
report_dir="${2:-/mnt/nas/openclaw/reports/baseline-status}"

case "$overnight_dir" in
  /mnt/nas/openclaw/logs/overnight|/mnt/nas/openclaw/logs/overnight/*|/tmp/*) ;;
  *)
    echo "Refusing overnight directory outside approved paths: $overnight_dir" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/tmp/*) ;;
  *)
    echo "Refusing report directory outside approved paths: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"

latest_jsonl="$(find "$overnight_dir" -maxdepth 1 -type f -name 'overnight_baseline_*.jsonl' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
if [[ -z "$latest_jsonl" ]]; then
  echo "No overnight baseline JSONL found under $overnight_dir" >&2
  exit 1
fi

base_name="$(basename "$latest_jsonl" .jsonl)"
pid_file="$overnight_dir/$base_name.pid"
summary="$report_dir/${base_name}_status.md"

pid="unknown"
if [[ -f "$pid_file" ]]; then
  pid="$(tr -cd '0-9' < "$pid_file")"
fi

process_status="unknown"
process_line=""
if [[ "$pid" != "unknown" && -n "$pid" ]]; then
  if process_line="$(ps -p "$pid" -o pid=,etime=,cmd= 2>/dev/null)"; then
    process_status="running"
  else
    process_status="not_running"
  fi
fi

python3 - "$latest_jsonl" "$summary" "$pid" "$process_status" "$process_line" <<'PY'
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

jsonl, summary, pid, process_status, process_line = sys.argv[1:6]
events = []
with open(jsonl, encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"time": "unknown", "level": "error", "action": "json_parse", "status": "bad_line", "detail": line})

iterations = sorted({int(e.get("iteration", 0)) for e in events if str(e.get("iteration", "")).isdigit()})
status_counts = Counter(e.get("status", "unknown") for e in events)
action_counts = Counter(e.get("action", "unknown") for e in events)
failed = [e for e in events if str(e.get("status", "")).startswith("failed") or e.get("level") == "error"]
last = events[-1] if events else {}

def parse_event_time(value):
    if not value or value == "unknown":
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None

runner_start = next((e for e in events if e.get("action") == "runner_start"), {})
interval_seconds = None
match = re.search(r"interval_seconds=(\d+)", str(runner_start.get("detail", "")))
if match:
    interval_seconds = int(match.group(1))

last_iteration_end = None
for event in events:
    if event.get("action") == "iteration_end":
        last_iteration_end = event

now = datetime.now().astimezone()
last_iteration_time = parse_event_time(last_iteration_end.get("time")) if last_iteration_end else None
next_iteration_after = None
seconds_until_next = None
staleness = "unknown"
if interval_seconds and last_iteration_time:
    next_iteration_after = last_iteration_time + timedelta(seconds=interval_seconds)
    seconds_until_next = int((next_iteration_after - now).total_seconds())
    if process_status == "running" and seconds_until_next >= 0:
        staleness = "waiting_for_next_interval"
    elif process_status == "running" and abs(seconds_until_next) <= max(300, interval_seconds // 2):
        staleness = "due_or_running_now"
    elif process_status == "running":
        staleness = "late_check_runner"
    else:
        staleness = "not_running"

latest_by_action = {}
for e in events:
    latest_by_action[e.get("action", "unknown")] = e

Path(summary).parent.mkdir(parents=True, exist_ok=True)
with open(summary, "w", encoding="utf-8") as out:
    out.write("# Overnight Baseline Runner Status\n\n")
    out.write(f"- generated_at: {datetime.now().astimezone().isoformat()}\n")
    out.write(f"- source_jsonl: {jsonl}\n")
    out.write(f"- pid: {pid}\n")
    out.write(f"- process_status: {process_status}\n")
    if process_line:
        out.write(f"- process_line: `{process_line.strip()}`\n")
    out.write(f"- event_count: {len(events)}\n")
    out.write(f"- completed_iterations_observed: {max(iterations) if iterations else 0}\n")
    out.write(f"- last_event_time: {last.get('time', 'missing')}\n")
    out.write(f"- last_event_action: {last.get('action', 'missing')}\n")
    out.write(f"- last_event_status: {last.get('status', 'missing')}\n")
    out.write(f"- interval_seconds: {interval_seconds if interval_seconds else 'unknown'}\n")
    out.write(f"- next_iteration_after: {next_iteration_after.isoformat() if next_iteration_after else 'unknown'}\n")
    out.write(f"- seconds_until_next_iteration: {seconds_until_next if seconds_until_next is not None else 'unknown'}\n")
    out.write(f"- schedule_status: {staleness}\n")
    out.write(f"- failed_event_count: {len(failed)}\n\n")

    out.write("## Status Counts\n\n")
    out.write("| Status | Count |\n| --- | --- |\n")
    for status, count in sorted(status_counts.items()):
        out.write(f"| {status} | {count} |\n")

    out.write("\n## Action Counts\n\n")
    out.write("| Action | Count |\n| --- | --- |\n")
    for action, count in sorted(action_counts.items()):
        out.write(f"| {action} | {count} |\n")

    out.write("\n## Latest Events By Action\n\n")
    out.write("| Action | Time | Status | Detail |\n| --- | --- | --- | --- |\n")
    for action in sorted(latest_by_action):
        e = latest_by_action[action]
        detail = str(e.get("detail", "")).replace("|", "\\|")
        out.write(f"| {action} | {e.get('time', '')} | {e.get('status', '')} | {detail} |\n")

    out.write("\n## Failed Events\n\n")
    if failed:
        out.write("| Time | Action | Status | Detail |\n| --- | --- | --- | --- |\n")
        for e in failed:
            detail = str(e.get("detail", "")).replace("|", "\\|")
            out.write(f"| {e.get('time', '')} | {e.get('action', '')} | {e.get('status', '')} | {detail} |\n")
    else:
        out.write("No failed events recorded in the JSONL so far.\n")

print(summary)
PY
