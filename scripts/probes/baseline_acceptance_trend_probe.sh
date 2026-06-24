#!/usr/bin/env bash
set -euo pipefail

nas_root="${1:-/mnt/nas/openclaw}"
report_dir="${2:-$nas_root/reports/baseline-status}"

case "$nas_root" in
  /mnt/nas/openclaw|/mnt/nas/openclaw/*|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/tmp/*) ;;
  *)
    echo "Refusing NAS/workspace root outside approved paths: $nas_root" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing report directory outside approved paths: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/baseline_acceptance_trend_$stamp.md"
json="$report_dir/baseline_acceptance_trend_$stamp.json"

python3 - "$nas_root" "$report" "$json" <<'PY'
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

nas_root = Path(sys.argv[1])
report = Path(sys.argv[2])
json_path = Path(sys.argv[3])

json_files = sorted(
    nas_root.glob("reports/baseline-status/baseline_acceptance_[0-9]*.json"),
    key=lambda path: path.stat().st_mtime if path.exists() else 0,
)

runs = []
for path in json_files:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        runs.append({
            "path": str(path),
            "generated_at": "unknown",
            "overall": "unreadable",
            "status_counts": {"unreadable": 1},
            "items": [],
            "error": str(exc),
        })
        continue
    payload["_path"] = str(path)
    runs.append(payload)

by_id = defaultdict(list)
for run in runs:
    generated_at = run.get("generated_at", "unknown")
    for item in run.get("items", []):
        by_id[item.get("id", "unknown")].append({
            "generated_at": generated_at,
            "status": item.get("status", "unknown"),
            "title": item.get("title", ""),
            "evidence": item.get("evidence", ""),
            "next_action": item.get("next_action", ""),
            "report": run.get("report") or run.get("_path", ""),
        })

item_rows = []
for item_id in sorted(by_id):
    history = by_id[item_id]
    first = history[0]
    latest = history[-1]
    statuses = [entry["status"] for entry in history]
    changed = len(set(statuses)) > 1
    item_rows.append({
        "id": item_id,
        "title": latest["title"],
        "first_status": first["status"],
        "latest_status": latest["status"],
        "changed": changed,
        "observations": len(history),
        "latest_next_action": latest["next_action"],
        "latest_evidence": latest["evidence"],
    })

latest_run = runs[-1] if runs else {}
latest_counts = latest_run.get("status_counts", {})
overall = latest_run.get("overall", "missing")
not_ready = [
    row for row in item_rows
    if row["latest_status"] != "pass"
]

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "read-only acceptance trend; no system changes executed",
    "nas_root": str(nas_root),
    "report": str(report),
    "source_count": len(runs),
    "latest_overall": overall,
    "latest_status_counts": latest_counts,
    "changed_items": [row for row in item_rows if row["changed"]],
    "not_ready_items": not_ready,
    "items": item_rows,
    "source_reports": [
        {
            "generated_at": run.get("generated_at", "unknown"),
            "overall": run.get("overall", "unknown"),
            "report": run.get("report") or run.get("_path", ""),
            "json": run.get("_path", ""),
            "status_counts": run.get("status_counts", {}),
        }
        for run in runs
    ],
}

json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

with report.open("w", encoding="utf-8") as out:
    out.write("# Baseline Acceptance Trend\n\n")
    out.write(f"- generated_at: {payload['generated_at']}\n")
    out.write("- mode: read-only acceptance trend; no system changes executed\n")
    out.write(f"- nas_root: {nas_root}\n")
    out.write(f"- report: {report}\n")
    out.write(f"- json: {json_path}\n")
    out.write(f"- source_count: {len(runs)}\n")
    out.write(f"- latest_overall: {overall}\n\n")

    out.write("## Latest Status Counts\n\n")
    out.write("| Status | Count |\n| --- | --- |\n")
    for status, count in sorted(Counter(latest_counts).items()):
        out.write(f"| {status} | {count} |\n")

    out.write("\n## Changed Items\n\n")
    if payload["changed_items"]:
        out.write("| ID | Title | First status | Latest status | Observations |\n| --- | --- | --- | --- | --- |\n")
        for row in payload["changed_items"]:
            out.write(f"| {row['id']} | {row['title']} | {row['first_status']} | {row['latest_status']} | {row['observations']} |\n")
    else:
        out.write("No item status changes across available acceptance reports.\n")

    out.write("\n## Not Ready Items\n\n")
    if not_ready:
        out.write("| ID | Latest status | Required action |\n| --- | --- | --- |\n")
        for row in not_ready:
            action = row["latest_next_action"].replace("|", "\\|")
            out.write(f"| {row['id']} | {row['latest_status']} | {action} |\n")
    else:
        out.write("All latest items are pass.\n")

    out.write("\n## Full Item Trend\n\n")
    out.write("| ID | Title | First status | Latest status | Changed | Observations |\n| --- | --- | --- | --- | --- | --- |\n")
    for row in item_rows:
        out.write(
            f"| {row['id']} | {row['title']} | {row['first_status']} | "
            f"{row['latest_status']} | {str(row['changed']).lower()} | {row['observations']} |\n"
        )

    out.write("\n## Source Reports\n\n")
    out.write("| Generated at | Overall | Report |\n| --- | --- | --- |\n")
    for run in payload["source_reports"]:
        out.write(f"| {run['generated_at']} | {run['overall']} | {run['report']} |\n")

print(report)
PY
