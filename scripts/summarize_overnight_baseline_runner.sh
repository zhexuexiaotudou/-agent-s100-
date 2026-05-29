#!/usr/bin/env bash
set -euo pipefail

overnight_dir="${1:-/mnt/nas/openclaw/logs/overnight}"
report_dir="${2:-/mnt/nas/openclaw/reports/baseline-status}"
nas_root="${3:-/mnt/nas/openclaw}"

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

case "$nas_root" in
  /mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
  *)
    echo "Refusing NAS root outside approved paths: $nas_root" >&2
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
summary="$report_dir/${base_name}_summary.md"

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

latest_file() {
  local dir="$1"
  local pattern="$2"
  find "$dir" -type f -name "$pattern" -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}'
}

latest_stability="$(latest_file "$nas_root/reports/stability" 'stability_summary_*.md')"
latest_baseline="$(latest_file "$nas_root/reports/baseline-status" 'baseline_status_*.md')"
latest_gap="$(latest_file "$nas_root/reports/baseline-status" 'baseline_gap_decision_*.md')"
latest_security="$(latest_file "$nas_root/logs/probes" 'security_audit_*.md')"
latest_convergence="$(latest_file "$nas_root/reports/security" 'service_convergence_decision_*.md')"
latest_execution_preflight="$(latest_file "$nas_root/reports/security" 'service_execution_preflight_*.md')"

python3 - "$latest_jsonl" "$summary" "$pid" "$process_status" "$process_line" "$latest_stability" "$latest_baseline" "$latest_gap" "$latest_security" "$latest_convergence" "$latest_execution_preflight" <<'PY'
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

(
    jsonl,
    summary,
    pid,
    process_status,
    process_line,
    latest_stability,
    latest_baseline,
    latest_gap,
    latest_security,
    latest_convergence,
    latest_execution_preflight,
) = sys.argv[1:12]

events = []
with open(jsonl, encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({
                "time": "unknown",
                "iteration": 0,
                "level": "error",
                "action": "json_parse",
                "status": "bad_line",
                "detail": line,
            })

def latest_detail(action):
    for event in reversed(events):
        if event.get("action") == action:
            return str(event.get("detail", ""))
    return ""

def extract_field(path, label):
    if not path:
        return "missing"
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "unreadable"
    pattern = re.compile(rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|")
    match = pattern.search(text)
    return match.group(1).strip() if match else "missing"

iterations = sorted({
    int(event.get("iteration", 0))
    for event in events
    if str(event.get("iteration", "")).isdigit() and int(event.get("iteration", 0)) > 0
})
status_counts = Counter(event.get("status", "unknown") for event in events)
action_counts = Counter(event.get("action", "unknown") for event in events)
failed = [
    event for event in events
    if str(event.get("status", "")).startswith("failed") or event.get("level") == "error"
]
runner_finish = next((event for event in reversed(events) if event.get("action") == "runner_finish"), None)

snapshot_count = extract_field(latest_stability, "Snapshot count")
elapsed_hours = extract_field(latest_stability, "Elapsed hours")
gateway_status = extract_field(latest_baseline, "OpenClaw Gateway")
nas_status = extract_field(latest_baseline, "NAS workspace")
allowlisted_count = extract_field(latest_baseline, "Allowlisted tool count")

if process_status == "running":
    verdict = "collecting"
elif runner_finish and not failed:
    verdict = "complete_no_failed_events"
elif runner_finish and failed:
    verdict = "complete_with_failures"
else:
    verdict = "stopped_without_finish_event"

Path(summary).parent.mkdir(parents=True, exist_ok=True)
with open(summary, "w", encoding="utf-8") as out:
    out.write("# Overnight Baseline Runner Summary\n\n")
    out.write(f"- generated_at: {datetime.now().astimezone().isoformat()}\n")
    out.write(f"- source_jsonl: {jsonl}\n")
    out.write(f"- pid: {pid}\n")
    out.write(f"- process_status: {process_status}\n")
    if process_line:
        out.write(f"- process_line: `{process_line.strip()}`\n")
    out.write(f"- verdict: {verdict}\n")
    out.write(f"- event_count: {len(events)}\n")
    out.write(f"- completed_iterations_observed: {max(iterations) if iterations else 0}\n")
    out.write(f"- failed_event_count: {len(failed)}\n\n")

    out.write("## Latest Baseline Evidence\n\n")
    out.write("| Check | Value |\n| --- | --- |\n")
    out.write(f"| latest_stability_summary | {latest_stability or 'missing'} |\n")
    out.write(f"| snapshot_count | {snapshot_count} |\n")
    out.write(f"| elapsed_hours | {elapsed_hours} |\n")
    out.write(f"| latest_baseline_status | {latest_baseline or 'missing'} |\n")
    out.write(f"| latest_baseline_gap_decision | {latest_gap or 'missing'} |\n")
    out.write(f"| gateway_status | {gateway_status} |\n")
    out.write(f"| nas_status | {nas_status} |\n")
    out.write(f"| allowlisted_tool_count | {allowlisted_count} |\n")
    out.write(f"| latest_security_audit | {latest_security or 'missing'} |\n")
    out.write(f"| latest_service_convergence_decision | {latest_convergence or 'missing'} |\n")
    out.write(f"| latest_service_execution_preflight | {latest_execution_preflight or 'missing'} |\n")

    out.write("\n## Action Counts\n\n")
    out.write("| Action | Count |\n| --- | --- |\n")
    for action, count in sorted(action_counts.items()):
        out.write(f"| {action} | {count} |\n")

    out.write("\n## Status Counts\n\n")
    out.write("| Status | Count |\n| --- | --- |\n")
    for status, count in sorted(status_counts.items()):
        out.write(f"| {status} | {count} |\n")

    out.write("\n## Latest Tool Outputs\n\n")
    out.write("| Action | Latest detail |\n| --- | --- |\n")
    for action in [
        "stability_snapshot",
        "stability_summary",
        "baseline_status",
        "baseline_gap_decision",
        "openclaw_status",
        "security_audit",
        "service_convergence_decision",
        "service_execution_preflight",
        "runner_finish",
    ]:
        detail = latest_detail(action).replace("|", "\\|") or "missing"
        out.write(f"| {action} | {detail} |\n")

    out.write("\n## Failed Events\n\n")
    if failed:
        out.write("| Time | Iteration | Action | Status | Detail |\n| --- | --- | --- | --- | --- |\n")
        for event in failed:
            detail = str(event.get("detail", "")).replace("|", "\\|")
            out.write(
                f"| {event.get('time', '')} | {event.get('iteration', '')} | "
                f"{event.get('action', '')} | {event.get('status', '')} | {detail} |\n"
            )
    else:
        out.write("No failed events recorded.\n")

    out.write("\n## Acceptance Meaning\n\n")
    out.write("- `collecting` means the overnight run is still active and this report is an interim checkpoint.\n")
    out.write("- `complete_no_failed_events` means the configured overnight window finished without failed JSONL events.\n")
    out.write("- This overnight report does not replace the 168-hour A-010 acceptance window.\n")

print(summary)
PY
