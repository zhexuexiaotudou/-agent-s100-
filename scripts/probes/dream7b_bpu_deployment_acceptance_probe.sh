#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
min_batch_capacity="${DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY:-16}"
min_systemd_batch_requests="${DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS:-16}"
min_systemd_telemetry_requests="${DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS:-48}"
min_long_repeat_count="${DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT:-6}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$min_batch_capacity" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_systemd_batch_requests" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_systemd_telemetry_requests" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_long_repeat_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT must be a positive integer." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_deployment_acceptance_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$report_root" \
  "$min_batch_capacity" \
  "$min_systemd_batch_requests" \
  "$min_systemd_telemetry_requests" \
  "$min_long_repeat_count" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
min_batch_capacity = int(sys.argv[3])
min_systemd_batch_requests = int(sys.argv[4])
min_systemd_telemetry_requests = int(sys.argv[5])
min_long_repeat_count = int(sys.argv[6])
errors = []
warnings = []
checks = []


def latest_json(pattern):
    paths = [Path(item) for item in glob.glob(str(report_root / pattern))]
    paths = [item for item in paths if item.is_file()]
    if not paths:
        return None, None
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def add_check(name, path, ok, details):
    row = {
        "name": name,
        "ok": bool(ok),
        "path": str(path) if path else "",
        "details": details,
    }
    checks.append(row)
    if not ok:
        errors.append(f"{name} failed: {details}")


systemd_path, systemd = latest_json("dream7b_bpu_batch_queue_systemd_*/systemd_probe.json")
if systemd is None:
    add_check("systemd_service", systemd_path, False, {"reason": "missing systemd_probe.json"})
else:
    ok = (
        systemd.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_probe"
        and systemd.get("service_status") == "active"
        and systemd.get("service_enabled") == "enabled"
        and systemd.get("max_batch_size_required") == 16
        and systemd.get("drain_all_required") is True
        and "--max-batch-size 16" in (systemd.get("exec_start") or "")
        and "--drain-all" in (systemd.get("exec_start") or "")
        and not systemd.get("errors")
    )
    add_check(
        "systemd_service",
        systemd_path,
        ok,
        {
            "verdict": systemd.get("verdict"),
            "service_status": systemd.get("service_status"),
            "service_enabled": systemd.get("service_enabled"),
            "max_batch_size_required": systemd.get("max_batch_size_required"),
            "drain_all_required": systemd.get("drain_all_required"),
        },
    )

capacity_path, capacity = latest_json("dream7b_bpu_batch_capacity_*/batch_capacity_probe.json")
if capacity is None:
    add_check("batch_capacity", capacity_path, False, {"reason": "missing batch_capacity_probe.json"})
else:
    entries = capacity.get("entries") or []
    batch16 = [item for item in entries if item.get("batch_count") == min_batch_capacity]
    batch16_entry = batch16[-1] if batch16 else {}
    ok = (
        capacity.get("verdict") == "ok_dream7b_bpu_batch_capacity_probe"
        and int(capacity.get("max_passing_count") or 0) >= min_batch_capacity
        and bool(batch16_entry.get("ok"))
        and batch16_entry.get("execution_mode") == "pair_window_batch"
        and batch16_entry.get("window_execution_mode") == "window-batch"
        and batch16_entry.get("child_process_count") == 0
        and batch16_entry.get("final_shape_count") == min_batch_capacity
        and not capacity.get("errors")
    )
    add_check(
        "batch_capacity",
        capacity_path,
        ok,
        {
            "verdict": capacity.get("verdict"),
            "max_passing_count": capacity.get("max_passing_count"),
            "batch_count": batch16_entry.get("batch_count"),
            "amortized_wall_ms_per_forward": batch16_entry.get("amortized_wall_ms_per_forward"),
        },
    )

systemd_batch_path, systemd_batch = latest_json("dream7b_bpu_batch_queue_systemd_batch_*/systemd_batch_probe.json")
if systemd_batch is None:
    add_check("systemd_batch", systemd_batch_path, False, {"reason": "missing systemd_batch_probe.json"})
else:
    ok = (
        systemd_batch.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_batch_probe"
        and systemd_batch.get("job_status") == "done"
        and int(systemd_batch.get("request_count") or 0) >= min_systemd_batch_requests
        and int(systemd_batch.get("processed_count") or 0) >= min_systemd_batch_requests
        and systemd_batch.get("accepted_count") == systemd_batch.get("processed_count")
        and systemd_batch.get("deferred_count") == 0
        and systemd_batch.get("max_batch_size") == 16
        and systemd_batch.get("batch_run_count") == 1
        and systemd_batch.get("batch_count") == systemd_batch.get("processed_count")
        and systemd_batch.get("execution_mode") == "pair_window_batch"
        and systemd_batch.get("window_execution_mode") == "window-batch"
        and systemd_batch.get("child_process_count") == 0
        and not systemd_batch.get("errors")
    )
    add_check(
        "systemd_batch",
        systemd_batch_path,
        ok,
        {
            "verdict": systemd_batch.get("verdict"),
            "processed_count": systemd_batch.get("processed_count"),
            "batch_count": systemd_batch.get("batch_count"),
            "amortized_wall_ms_per_processed_request": systemd_batch.get("amortized_wall_ms_per_processed_request"),
        },
    )

systemd_drain_path, systemd_drain = latest_json("dream7b_bpu_batch_queue_systemd_drain_*/systemd_drain_probe.json")
if systemd_drain is None:
    add_check("systemd_drain", systemd_drain_path, False, {"reason": "missing systemd_drain_probe.json"})
else:
    ok = (
        systemd_drain.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_drain_probe"
        and systemd_drain.get("job_status") == "done"
        and int(systemd_drain.get("request_count") or 0) >= min_systemd_batch_requests
        and systemd_drain.get("drain_all") is True
        and systemd_drain.get("max_batch_size") == 16
        and systemd_drain.get("processed_count") == systemd_drain.get("request_count")
        and systemd_drain.get("accepted_count") == systemd_drain.get("request_count")
        and systemd_drain.get("deferred_count") == 0
        and systemd_drain.get("batch_counts") == [16]
        and not systemd_drain.get("errors")
    )
    add_check(
        "systemd_drain",
        systemd_drain_path,
        ok,
        {
            "verdict": systemd_drain.get("verdict"),
            "request_count": systemd_drain.get("request_count"),
            "batch_counts": systemd_drain.get("batch_counts"),
            "amortized_wall_ms_per_processed_request": systemd_drain.get("amortized_wall_ms_per_processed_request"),
        },
    )

systemd_canary_path, systemd_canary = latest_json("dream7b_bpu_batch_queue_systemd_canary_*/systemd_canary_probe.json")
if systemd_canary is None:
    add_check("systemd_canary", systemd_canary_path, False, {"reason": "missing systemd_canary_probe.json"})
else:
    ok = (
        systemd_canary.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_canary_probe"
        and systemd_canary.get("service_status_before") == "active"
        and systemd_canary.get("service_enabled_before") == "enabled"
        and systemd_canary.get("service_status_after") == "active"
        and systemd_canary.get("service_enabled_after") == "enabled"
        and systemd_canary.get("job_status") == "done"
        and int(systemd_canary.get("request_count") or 0) >= 1
        and systemd_canary.get("request_count") == systemd_canary.get("processed_count")
        and systemd_canary.get("request_count") == systemd_canary.get("accepted_count")
        and systemd_canary.get("deferred_count") == 0
        and systemd_canary.get("skipped_count") == 0
        and systemd_canary.get("drain_all") is True
        and systemd_canary.get("max_batch_size") == 16
        and systemd_canary.get("batch_run_count") == 1
        and systemd_canary.get("batch_count") == systemd_canary.get("request_count")
        and systemd_canary.get("result_count") == systemd_canary.get("request_count")
        and systemd_canary.get("execution_mode") == "pair_window_batch"
        and systemd_canary.get("window_execution_mode") == "window-batch"
        and systemd_canary.get("child_process_count") == 0
        and systemd_canary.get("bpu_lock_path") == "/run/lock/dream7b_bpu_batch_queue_runner.lock"
        and all(item == [1, 16, 152064] for item in (systemd_canary.get("final_shapes") or []))
        and not systemd_canary.get("errors")
    )
    add_check(
        "systemd_canary",
        systemd_canary_path,
        ok,
        {
            "verdict": systemd_canary.get("verdict"),
            "job_status": systemd_canary.get("job_status"),
            "request_count": systemd_canary.get("request_count"),
            "processed_count": systemd_canary.get("processed_count"),
            "final_shapes": systemd_canary.get("final_shapes"),
            "amortized_wall_ms_per_processed_request": systemd_canary.get("amortized_wall_ms_per_processed_request"),
        },
    )

systemd_telemetry_path, systemd_telemetry = latest_json("dream7b_bpu_batch_queue_systemd_telemetry_*/systemd_telemetry_probe.json")
if systemd_telemetry is None:
    add_check("systemd_telemetry", systemd_telemetry_path, False, {"reason": "missing systemd_telemetry_probe.json"})
else:
    ok = (
        systemd_telemetry.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe"
        and int(systemd_telemetry.get("processed_request_count") or 0) >= min_systemd_telemetry_requests
        and systemd_telemetry.get("failed_job_count") == 0
        and systemd_telemetry.get("deferred_request_count") == 0
        and all(item == 16 for item in (systemd_telemetry.get("batch_counts") or []))
        and float(systemd_telemetry.get("max_bpu_loading") or 0.0) > 0.0
        and int(systemd_telemetry.get("nonzero_bpu_loading_sample_count") or 0) > 0
        and not systemd_telemetry.get("errors")
    )
    add_check(
        "systemd_telemetry",
        systemd_telemetry_path,
        ok,
        {
            "verdict": systemd_telemetry.get("verdict"),
            "processed_request_count": systemd_telemetry.get("processed_request_count"),
            "batch_counts": systemd_telemetry.get("batch_counts"),
            "max_bpu_loading": systemd_telemetry.get("max_bpu_loading"),
            "avg_bpu_loading": systemd_telemetry.get("avg_bpu_loading"),
        },
    )

long_repeat_path, long_repeat = latest_json("dream7b_bpu_fine_forward_long_repeat_*/long_repeat_probe.json")
if long_repeat is None:
    add_check("long_repeat", long_repeat_path, False, {"reason": "missing long_repeat_probe.json"})
else:
    results = long_repeat.get("results") or []
    ok = (
        long_repeat.get("verdict") == "ok_dream7b_bpu_fine_forward_long_repeat_probe"
        and int(long_repeat.get("repeat_count") or 0) >= min_long_repeat_count
        and long_repeat.get("repeat_status") == 0
        and long_repeat.get("failure_count") == 0
        and all(item.get("execution_mode") == "pair_in_process" for item in results)
        and all(item.get("window_execution_mode") == "in-process" for item in results)
        and all(item.get("child_process_count") == 0 for item in results)
        and all(item.get("segment_count") == 10 for item in results)
        and all(item.get("final_shape") == [1, 16, 152064] for item in results)
        and not long_repeat.get("errors")
    )
    add_check(
        "long_repeat",
        long_repeat_path,
        ok,
        {
            "verdict": long_repeat.get("verdict"),
            "repeat_count": long_repeat.get("repeat_count"),
            "failure_count": long_repeat.get("failure_count"),
            "median_wall_ms": long_repeat.get("median_wall_ms"),
            "wall_spread_ratio": long_repeat.get("wall_spread_ratio"),
        },
    )

retention_path, retention = latest_json("dream7b_bpu_batch_queue_retention_*/queue_retention_probe.json")
if retention is None:
    add_check("queue_retention", retention_path, False, {"reason": "missing queue_retention_probe.json"})
else:
    ok = (
        retention.get("verdict") == "ok_dream7b_bpu_batch_queue_retention_probe"
        and retention.get("policy_mode") == "report_only"
        and retention.get("pending_stale_count") == 0
        and retention.get("processing_stale_count") == 0
        and (retention.get("archive_plan") or {}).get("apply_supported") is False
        and not retention.get("errors")
    )
    add_check(
        "queue_retention",
        retention_path,
        ok,
        {
            "verdict": retention.get("verdict"),
            "policy_mode": retention.get("policy_mode"),
            "queue_counts": retention.get("queue_counts"),
            "pending_stale_count": retention.get("pending_stale_count"),
            "processing_stale_count": retention.get("processing_stale_count"),
            "apply_supported": (retention.get("archive_plan") or {}).get("apply_supported"),
        },
    )

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_deployment_acceptance_probe" if not errors else "failed_dream7b_bpu_deployment_acceptance_probe",
    "report_root": str(report_root),
    "run_dir": str(run_dir),
    "min_batch_capacity": min_batch_capacity,
    "min_systemd_batch_requests": min_systemd_batch_requests,
    "min_systemd_telemetry_requests": min_systemd_telemetry_requests,
    "min_long_repeat_count": min_long_repeat_count,
    "check_count": len(checks),
    "passed_check_count": sum(1 for item in checks if item["ok"]),
    "checks": checks,
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "deployment_acceptance_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
check_lines = [
    f"| {item['name']} | {item['ok']} | {item['path']} | `{json.dumps(item['details'], ensure_ascii=False)}` |"
    for item in checks
]
warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
(run_dir / "deployment_acceptance_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU Deployment Acceptance Probe",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- report_root: {payload['report_root']}",
        f"- run_dir: {payload['run_dir']}",
        f"- check_count: {payload['check_count']}",
        f"- passed_check_count: {payload['passed_check_count']}",
        f"- min_batch_capacity: {payload['min_batch_capacity']}",
        f"- min_systemd_batch_requests: {payload['min_systemd_batch_requests']}",
        f"- min_systemd_telemetry_requests: {payload['min_systemd_telemetry_requests']}",
        f"- min_long_repeat_count: {payload['min_long_repeat_count']}",
        "",
        "## Checks",
        "",
        "| name | ok | path | details |",
        "| --- | --- | --- | --- |",
        *check_lines,
        "",
        "## Warnings",
        "",
        *warning_lines,
        "",
        "## Errors",
        "",
        *error_lines,
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "deployment_acceptance_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
