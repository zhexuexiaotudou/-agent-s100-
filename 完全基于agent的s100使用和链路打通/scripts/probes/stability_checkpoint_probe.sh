#!/usr/bin/env bash
set -euo pipefail

input_dir="${1:-/root/.openclaw/workspace/logs/probes}"
report_dir="${2:-/root/.openclaw/workspace/reports/stability}"
target_hours="${3:-168}"
max_gap_hours="${4:-2}"

case "$input_dir" in
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing input path outside approved stability snapshot directories: $input_dir" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing report directory outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

case "$target_hours" in
  ''|*[!0-9]*)
    echo "Refusing non-integer target hours: $target_hours" >&2
    exit 2
    ;;
esac

case "$max_gap_hours" in
  ''|*[!0-9.]*)
    echo "Refusing non-numeric max gap hours: $max_gap_hours" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/stability_checkpoint_$stamp.md"
json="$report_dir/stability_checkpoint_$stamp.json"

python3 - "$input_dir" "$report" "$json" "$target_hours" "$max_gap_hours" <<'PY'
import json
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

input_dir = Path(sys.argv[1])
report = Path(sys.argv[2])
json_path = Path(sys.argv[3])
target_hours = int(sys.argv[4])
max_gap_hours = float(sys.argv[5])


def latest(pattern: str):
    files = sorted(
        input_dir.glob(pattern),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    return files[0] if files else None


def read_text(path):
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def metadata(text: str, field: str) -> str:
    match = re.search(rf"^- {re.escape(field)}:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def table_value(text: str, field: str) -> str:
    for line in text.splitlines():
        if line.startswith("|") and f"| {field} |" in line:
            parts = [part.strip() for part in line.strip("|").split("|")]
            if len(parts) >= 2:
                return parts[1]
    return ""


def parse_time(value: str):
    if not value or value == "n/a":
        return None
    value = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def to_float(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


snapshots = sorted(input_dir.glob("stability_snapshot_*.md"), key=lambda p: p.stat().st_mtime)
snapshot_times = []
gateway_bad = 0
oom_bad = 0
for snapshot in snapshots:
    text = read_text(snapshot)
    generated = parse_time(metadata(text, "generated_at"))
    if generated:
        snapshot_times.append(generated)
    gateway_errors = table_value(text, "Gateway error-like log matches in last 24h")
    oom_errors = table_value(text, "Kernel OOM matches in last 24h")
    try:
        gateway_bad += 1 if int(gateway_errors or "0") > 0 else 0
    except ValueError:
        gateway_bad += 1
    try:
        oom_bad += 1 if int(oom_errors or "0") > 0 else 0
    except ValueError:
        oom_bad += 1

summary_dir = report.parent
latest_summary = latest("../../reports/stability/stability_summary_*.md")
if latest_summary is None and summary_dir.exists():
    candidates = sorted(summary_dir.glob("stability_summary_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    latest_summary = candidates[0] if candidates else None

summary_text = read_text(latest_summary)
elapsed_hours = to_float(table_value(summary_text, "Elapsed hours"))
summary_verdict = table_value(summary_text, "Verdict") or "missing"

first_time = snapshot_times[0] if snapshot_times else None
last_time = snapshot_times[-1] if snapshot_times else None
if elapsed_hours is None and first_time and last_time:
    elapsed_hours = max(0.0, (last_time - first_time).total_seconds() / 3600)
elapsed_hours = elapsed_hours or 0.0

remaining_hours = max(0.0, target_hours - elapsed_hours)
eta = None
if last_time:
    eta = last_time + timedelta(hours=remaining_hours)

interval_hours = []
for prev, cur in zip(snapshot_times, snapshot_times[1:]):
    interval_hours.append((cur - prev).total_seconds() / 3600)
median_interval = statistics.median(interval_hours) if interval_hours else None
max_interval = max(interval_hours) if interval_hours else None

gap_events = []
continuous_start = first_time
if snapshot_times:
    for index, (prev, cur) in enumerate(zip(snapshot_times, snapshot_times[1:]), start=1):
        gap = (cur - prev).total_seconds() / 3600
        if gap > max_gap_hours:
            gap_events.append(
                {
                    "previous": prev.isoformat(),
                    "next": cur.isoformat(),
                    "gap_hours": round(gap, 2),
                    "next_snapshot_index": index + 1,
                }
            )
            continuous_start = cur

continuous_elapsed_hours = 0.0
continuous_remaining_hours = float(target_hours)
continuous_eta = None
if continuous_start and last_time:
    continuous_elapsed_hours = max(0.0, (last_time - continuous_start).total_seconds() / 3600)
    continuous_remaining_hours = max(0.0, target_hours - continuous_elapsed_hours)
    continuous_eta = last_time + timedelta(hours=continuous_remaining_hours)

sample_count = len(snapshots)
expected_samples = None
coverage_ratio = None
if median_interval and median_interval > 0:
    expected_samples = int(target_hours / median_interval) + 1
    coverage_ratio = min(1.0, sample_count / expected_samples)

if sample_count == 0:
    checkpoint_status = "no_samples"
elif continuous_remaining_hours > 0:
    checkpoint_status = "collecting"
elif summary_verdict == "candidate_7day_pass" and gateway_bad == 0 and oom_bad == 0 and not gap_events:
    checkpoint_status = "candidate_complete"
else:
    checkpoint_status = "needs_review"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "read-only A-010 stability checkpoint; no system changes executed",
    "input_dir": str(input_dir),
    "report": str(report),
    "latest_summary": str(latest_summary) if latest_summary else None,
    "target_hours": target_hours,
    "max_gap_hours": max_gap_hours,
    "snapshot_count": sample_count,
    "first_snapshot_at": first_time.isoformat() if first_time else None,
    "last_snapshot_at": last_time.isoformat() if last_time else None,
    "elapsed_hours": round(elapsed_hours, 2),
    "remaining_hours": round(remaining_hours, 2),
    "eta_at_current_span": eta.isoformat() if eta else None,
    "median_interval_hours": round(median_interval, 2) if median_interval is not None else None,
    "max_interval_hours": round(max_interval, 2) if max_interval is not None else None,
    "gap_event_count": len(gap_events),
    "largest_gap_hours": round(max_interval, 2) if max_interval is not None else None,
    "continuous_start_at": continuous_start.isoformat() if continuous_start else None,
    "continuous_elapsed_hours": round(continuous_elapsed_hours, 2),
    "continuous_remaining_hours": round(continuous_remaining_hours, 2),
    "continuous_eta": continuous_eta.isoformat() if continuous_eta else None,
    "expected_samples_at_median_interval": expected_samples,
    "coverage_ratio": round(coverage_ratio, 4) if coverage_ratio is not None else None,
    "summary_verdict": summary_verdict,
    "snapshots_with_gateway_errors": gateway_bad,
    "snapshots_with_oom_errors": oom_bad,
    "checkpoint_status": checkpoint_status,
    "gap_events": gap_events[-10:],
}

json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

with report.open("w", encoding="utf-8") as out:
    out.write("# A-010 Stability Checkpoint\n\n")
    out.write(f"- generated_at: {payload['generated_at']}\n")
    out.write("- mode: read-only A-010 stability checkpoint; no system changes executed\n")
    out.write(f"- input_dir: {input_dir}\n")
    out.write(f"- latest_summary: {payload['latest_summary'] or 'missing'}\n")
    out.write(f"- target_hours: {target_hours}\n")
    out.write(f"- max_gap_hours: {max_gap_hours}\n")
    out.write(f"- checkpoint_status: {checkpoint_status}\n\n")
    out.write("## Progress\n\n")
    out.write("| Check | Value |\n| --- | --- |\n")
    out.write(f"| Snapshot count | {sample_count} |\n")
    out.write(f"| First snapshot | {payload['first_snapshot_at'] or 'missing'} |\n")
    out.write(f"| Last snapshot | {payload['last_snapshot_at'] or 'missing'} |\n")
    out.write(f"| Elapsed hours | {payload['elapsed_hours']} |\n")
    out.write(f"| Remaining hours | {payload['remaining_hours']} |\n")
    out.write(f"| ETA at current span | {payload['eta_at_current_span'] or 'missing'} |\n")
    out.write(f"| Median interval hours | {payload['median_interval_hours'] if payload['median_interval_hours'] is not None else 'missing'} |\n")
    out.write(f"| Max interval hours | {payload['max_interval_hours'] if payload['max_interval_hours'] is not None else 'missing'} |\n")
    out.write(f"| Gap event count | {payload['gap_event_count']} |\n")
    out.write(f"| Continuous start | {payload['continuous_start_at'] or 'missing'} |\n")
    out.write(f"| Continuous elapsed hours | {payload['continuous_elapsed_hours']} |\n")
    out.write(f"| Continuous remaining hours | {payload['continuous_remaining_hours']} |\n")
    out.write(f"| Continuous ETA | {payload['continuous_eta'] or 'missing'} |\n")
    out.write(f"| Expected samples at median interval | {expected_samples if expected_samples is not None else 'missing'} |\n")
    out.write(f"| Coverage ratio | {payload['coverage_ratio'] if payload['coverage_ratio'] is not None else 'missing'} |\n")
    out.write(f"| Summary verdict | {summary_verdict} |\n")
    out.write(f"| Snapshots with gateway errors | {gateway_bad} |\n")
    out.write(f"| Snapshots with OOM errors | {oom_bad} |\n\n")
    out.write("## Recent Gap Events\n\n")
    if gap_events:
        out.write("| Previous snapshot | Next snapshot | Gap hours | Next snapshot index |\n")
        out.write("| --- | --- | ---: | ---: |\n")
        for gap in gap_events[-10:]:
            out.write(f"| {gap['previous']} | {gap['next']} | {gap['gap_hours']} | {gap['next_snapshot_index']} |\n")
    else:
        out.write("No gap events over the configured threshold.\n")
    out.write("\n")
    out.write("## Next Action\n\n")
    if checkpoint_status == "collecting":
        out.write("Continue scheduled read-only stability snapshots until the continuous target window is reached.\n")
    elif checkpoint_status == "candidate_complete":
        out.write("Generate final A-010 acceptance evidence and decide whether NAS-backed evidence is required for final baseline closure.\n")
    elif checkpoint_status == "needs_review":
        out.write("Review warning counters and summary verdict before accepting A-010.\n")
    else:
        out.write("Start or restore stability snapshot collection.\n")

print(report)
PY
