#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
queue_dir="${2:-/mnt/nas/openclaw/queues/dream7b-bpu}"
done_retention_days="${DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS:-14}"
failed_retention_days="${DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS:-30}"
pending_stale_minutes="${DREAM7B_BPU_QUEUE_RETENTION_PENDING_STALE_MINUTES:-60}"
processing_stale_minutes="${DREAM7B_BPU_QUEUE_RETENTION_PROCESSING_STALE_MINUTES:-60}"
max_list="${DREAM7B_BPU_QUEUE_RETENTION_MAX_LIST:-50}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$queue_dir" in
  /tmp/*|/mnt/nas/openclaw/queues|/mnt/nas/openclaw/queues/*|/root/.openclaw/workspace/queues|/root/.openclaw/workspace/queues/*) ;;
  *)
    echo "Refusing queue path outside approved queue directories: $queue_dir" >&2
    exit 2
    ;;
esac

if ! [[ "$done_retention_days" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS must be a non-negative integer." >&2
  exit 2
fi
if ! [[ "$failed_retention_days" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS must be a non-negative integer." >&2
  exit 2
fi
if ! [[ "$pending_stale_minutes" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_QUEUE_RETENTION_PENDING_STALE_MINUTES must be a non-negative integer." >&2
  exit 2
fi
if ! [[ "$processing_stale_minutes" =~ ^[0-9]+$ ]]; then
  echo "DREAM7B_BPU_QUEUE_RETENTION_PROCESSING_STALE_MINUTES must be a non-negative integer." >&2
  exit 2
fi
if ! [[ "$max_list" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_QUEUE_RETENTION_MAX_LIST must be a positive integer." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_batch_queue_retention_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$queue_dir" \
  "$done_retention_days" \
  "$failed_retention_days" \
  "$pending_stale_minutes" \
  "$processing_stale_minutes" \
  "$max_list" <<'PY'
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

run_dir = Path(sys.argv[1])
queue_dir = Path(sys.argv[2])
done_retention_days = int(sys.argv[3])
failed_retention_days = int(sys.argv[4])
pending_stale_minutes = int(sys.argv[5])
processing_stale_minutes = int(sys.argv[6])
max_list = int(sys.argv[7])
now = time.time()
queue_names = ("pending", "processing", "done", "failed")
errors = []
warnings = []


def iso_from_epoch(value):
    return datetime.fromtimestamp(value, timezone.utc).astimezone().isoformat()


def scan_queue(name):
    path = queue_dir / name
    rows = []
    if not path.is_dir():
        errors.append(f"missing queue subdirectory: {path}")
        return rows
    for item in sorted(path.glob("*.jsonl")):
        if not item.is_file():
            continue
        stat = item.stat()
        age_seconds = max(0.0, now - stat.st_mtime)
        rows.append(
            {
                "queue": name,
                "path": str(item),
                "name": item.name,
                "size_bytes": stat.st_size,
                "mtime": iso_from_epoch(stat.st_mtime),
                "age_seconds": round(age_seconds, 3),
                "age_minutes": round(age_seconds / 60.0, 3),
                "age_days": round(age_seconds / 86400.0, 6),
            }
        )
    return rows


rows_by_queue = {name: scan_queue(name) for name in queue_names}
pending_stale = [
    item for item in rows_by_queue["pending"]
    if item["age_minutes"] >= pending_stale_minutes
]
processing_stale = [
    item for item in rows_by_queue["processing"]
    if item["age_minutes"] >= processing_stale_minutes
]
done_archive_candidates = [
    item for item in rows_by_queue["done"]
    if item["age_days"] >= done_retention_days
]
failed_archive_candidates = [
    item for item in rows_by_queue["failed"]
    if item["age_days"] >= failed_retention_days
]
if processing_stale:
    warnings.append(f"stale processing jobs: {len(processing_stale)}")
if pending_stale:
    warnings.append(f"stale pending jobs: {len(pending_stale)}")

counts = {name: len(rows_by_queue[name]) for name in queue_names}
size_bytes = {
    name: sum(item["size_bytes"] for item in rows_by_queue[name])
    for name in queue_names
}
archive_root = queue_dir / "archive"
archive_plan = {
    "policy_mode": "report_only",
    "archive_root": str(archive_root),
    "done_archive_dir": str(archive_root / "done"),
    "failed_archive_dir": str(archive_root / "failed"),
    "done_retention_days": done_retention_days,
    "failed_retention_days": failed_retention_days,
    "pending_stale_minutes": pending_stale_minutes,
    "processing_stale_minutes": processing_stale_minutes,
    "apply_supported": False,
}


def limited(rows):
    return sorted(rows, key=lambda item: item["age_seconds"], reverse=True)[:max_list]


payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_batch_queue_retention_probe" if not errors else "failed_dream7b_bpu_batch_queue_retention_probe",
    "queue_dir": str(queue_dir),
    "run_dir": str(run_dir),
    "policy_mode": "report_only",
    "done_retention_days": done_retention_days,
    "failed_retention_days": failed_retention_days,
    "pending_stale_minutes": pending_stale_minutes,
    "processing_stale_minutes": processing_stale_minutes,
    "max_list": max_list,
    "queue_counts": counts,
    "queue_size_bytes": size_bytes,
    "pending_stale_count": len(pending_stale),
    "processing_stale_count": len(processing_stale),
    "done_archive_candidate_count": len(done_archive_candidates),
    "failed_archive_candidate_count": len(failed_archive_candidates),
    "pending_stale": limited(pending_stale),
    "processing_stale": limited(processing_stale),
    "done_archive_candidates": limited(done_archive_candidates),
    "failed_archive_candidates": limited(failed_archive_candidates),
    "archive_plan": archive_plan,
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "queue_retention_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def table_rows(rows):
    if not rows:
        return ["| none | | | | |"]
    return [
        f"| {item['name']} | {item['queue']} | {item['age_minutes']} | {item['size_bytes']} | {item['path']} |"
        for item in rows
    ]


warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines = [
    "# Dream 7B BPU Batch Queue Retention Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- queue_dir: {payload['queue_dir']}",
    f"- run_dir: {payload['run_dir']}",
    f"- policy_mode: {payload['policy_mode']}",
    f"- done_retention_days: {payload['done_retention_days']}",
    f"- failed_retention_days: {payload['failed_retention_days']}",
    f"- pending_stale_minutes: {payload['pending_stale_minutes']}",
    f"- processing_stale_minutes: {payload['processing_stale_minutes']}",
    f"- queue_counts: {payload['queue_counts']}",
    f"- queue_size_bytes: {payload['queue_size_bytes']}",
    f"- pending_stale_count: {payload['pending_stale_count']}",
    f"- processing_stale_count: {payload['processing_stale_count']}",
    f"- done_archive_candidate_count: {payload['done_archive_candidate_count']}",
    f"- failed_archive_candidate_count: {payload['failed_archive_candidate_count']}",
    f"- archive_root: {payload['archive_plan']['archive_root']}",
    f"- apply_supported: {payload['archive_plan']['apply_supported']}",
    "",
    "## Pending Stale",
    "",
    "| name | queue | age_minutes | size_bytes | path |",
    "| --- | --- | ---: | ---: | --- |",
    *table_rows(payload["pending_stale"]),
    "",
    "## Processing Stale",
    "",
    "| name | queue | age_minutes | size_bytes | path |",
    "| --- | --- | ---: | ---: | --- |",
    *table_rows(payload["processing_stale"]),
    "",
    "## Done Archive Candidates",
    "",
    "| name | queue | age_minutes | size_bytes | path |",
    "| --- | --- | ---: | ---: | --- |",
    *table_rows(payload["done_archive_candidates"]),
    "",
    "## Failed Archive Candidates",
    "",
    "| name | queue | age_minutes | size_bytes | path |",
    "| --- | --- | ---: | ---: | --- |",
    *table_rows(payload["failed_archive_candidates"]),
    "",
    "## Warnings",
    "",
    *warning_lines,
    "",
    "## Errors",
    "",
    *error_lines,
    "",
]
(run_dir / "queue_retention_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "queue_retention_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
