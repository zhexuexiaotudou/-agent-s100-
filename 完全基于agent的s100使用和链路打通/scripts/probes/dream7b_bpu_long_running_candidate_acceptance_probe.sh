#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
dry_run_report_root="${2:-/mnt/nas/openclaw/reports/personal-data-sort-dry-run}"
min_elapsed_sec="${DREAM7B_BPU_LONG_RUNNING_ACCEPT_MIN_ELAPSED_SEC:-1800}"
min_avg_bpu="${DREAM7B_BPU_LONG_RUNNING_ACCEPT_MIN_AVG_BPU:-45.0}"
max_load_to_run_ratio="${DREAM7B_BPU_LONG_RUNNING_ACCEPT_MAX_LOAD_TO_RUN_RATIO:-1.5}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$dry_run_report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing dry-run report path outside approved report directories: $dry_run_report_root" >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_long_running_candidate_acceptance_$stamp"
mkdir -p "$run_dir"

default_service_status="$run_dir/default_service_status.txt"
candidate_50pct_status="$run_dir/candidate_50pct_service_status.txt"
systemctl --no-pager --full status dream7b-bpu-batch-queue.service > "$default_service_status" 2>&1 || true
systemctl --no-pager --full status dream7b-bpu-selected-pair-cross-job-candidate-50pct.service > "$candidate_50pct_status" 2>&1 || true

python3 - \
  "$run_dir" \
  "$report_root" \
  "$dry_run_report_root" \
  "$min_elapsed_sec" \
  "$min_avg_bpu" \
  "$max_load_to_run_ratio" \
  "$default_service_status" \
  "$candidate_50pct_status" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
dry_run_report_root = Path(sys.argv[3])
min_elapsed_sec = int(sys.argv[4])
min_avg_bpu = float(sys.argv[5])
max_load_to_run_ratio = float(sys.argv[6])
default_service_status = Path(sys.argv[7])
candidate_50pct_status = Path(sys.argv[8])


def latest(pattern: str) -> Path | None:
    paths = [Path(item) for item in glob.glob(pattern) if Path(item).is_file()]
    if not paths:
        return None
    return max(paths, key=lambda item: item.stat().st_mtime)


def load_json(path: Path | None) -> dict:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


soak_path = latest(str(report_root / "dream7b_bpu_50pct_candidate_soak_*" / "50pct_candidate_soak_probe.json"))
dry_run_path = latest(str(dry_run_report_root / "personal_data_sort_*" / "personal_data_sort.json"))
service_plan_path = latest(str(report_root / "dream7b_bpu_selected_pair_cross_job_candidate_50pct_service_plan_*" / "service_plan.txt"))

soak = load_json(soak_path)
dry_run = load_json(dry_run_path)
service_plan_text = service_plan_path.read_text(encoding="utf-8", errors="replace") if service_plan_path else ""
default_status_text = default_service_status.read_text(encoding="utf-8", errors="replace")
candidate_status_text = candidate_50pct_status.read_text(encoding="utf-8", errors="replace")

errors = []
warnings = []

if not soak_path:
    errors.append("missing 50pct soak report")
elif soak.get("verdict") != "ok_dream7b_bpu_50pct_candidate_soak_probe":
    errors.append(f"unexpected soak verdict: {soak.get('verdict')}")
else:
    if int(soak.get("elapsed_sec") or 0) < min_elapsed_sec:
        errors.append(f"soak elapsed_sec below target: {soak.get('elapsed_sec')} < {min_elapsed_sec}")
    if int(soak.get("failed_job_count") if soak.get("failed_job_count") is not None else -1) != 0:
        errors.append(f"soak failed_job_count is nonzero: {soak.get('failed_job_count')}")
    if float(soak.get("avg_bpu_loading") or 0.0) < min_avg_bpu:
        errors.append(f"soak avg_bpu_loading below target: {soak.get('avg_bpu_loading')} < {min_avg_bpu}")
    if float(soak.get("max_iteration_load_to_run_ratio") or 999.0) > max_load_to_run_ratio:
        errors.append(
            "soak max_iteration_load_to_run_ratio above target: "
            f"{soak.get('max_iteration_load_to_run_ratio')} > {max_load_to_run_ratio}"
        )

if not service_plan_path:
    errors.append("missing 50pct service plan")
else:
    required_plan_terms = [
        "dream7b-bpu-selected-pair-cross-job-candidate-50pct.service",
        "max_batch_size: 192",
        "max_batch_size_limit: 256",
        "default_service_replaced: false",
        "default_service_name: dream7b-bpu-batch-queue.service",
    ]
    for term in required_plan_terms:
        if term not in service_plan_text:
            errors.append(f"service plan missing term: {term}")

if not dry_run_path:
    errors.append("missing Personal dry-run report")
else:
    if dry_run.get("verdict") != "ok_personal_data_sort_probe":
        errors.append(f"unexpected dry-run verdict: {dry_run.get('verdict')}")
    if dry_run.get("dry_run") is not True:
        errors.append(f"dry_run flag is not true: {dry_run.get('dry_run')}")
    if dry_run.get("upload_performed") is not False:
        errors.append(f"upload_performed is not false: {dry_run.get('upload_performed')}")
    if dry_run.get("delete_or_move_performed") is not False:
        errors.append(f"delete_or_move_performed is not false: {dry_run.get('delete_or_move_performed')}")
    if int(dry_run.get("file_count") or 0) < 1:
        errors.append(f"dry-run file_count below target: {dry_run.get('file_count')}")

if "Active: active (running)" not in default_status_text:
    errors.append("default dream7b-bpu-batch-queue.service is not active")
if "Loaded: loaded" in candidate_status_text and "could not be found" not in candidate_status_text:
    warnings.append("50pct candidate service appears installed; verify it was operator-approved")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_long_running_candidate_acceptance_probe" if not errors else "failed_dream7b_bpu_long_running_candidate_acceptance_probe",
    "run_dir": str(run_dir),
    "soak_json": str(soak_path) if soak_path else "",
    "dry_run_json": str(dry_run_path) if dry_run_path else "",
    "service_plan": str(service_plan_path) if service_plan_path else "",
    "default_service_status": str(default_service_status),
    "candidate_50pct_status": str(candidate_50pct_status),
    "min_elapsed_sec": min_elapsed_sec,
    "min_avg_bpu": min_avg_bpu,
    "max_load_to_run_ratio": max_load_to_run_ratio,
    "soak_elapsed_sec": soak.get("elapsed_sec"),
    "soak_iteration_count": soak.get("iteration_count"),
    "soak_processed_request_count": soak.get("processed_request_count"),
    "soak_failed_job_count": soak.get("failed_job_count"),
    "soak_avg_bpu_loading": soak.get("avg_bpu_loading"),
    "soak_max_iteration_load_to_run_ratio": soak.get("max_iteration_load_to_run_ratio"),
    "dry_run_file_count": dry_run.get("file_count"),
    "dry_run_upload_performed": dry_run.get("upload_performed"),
    "default_service_replaced": False,
    "rollback_status": "rollback_safe_candidate_only",
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "long_running_candidate_acceptance_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B Long-Running Candidate Acceptance",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- soak_json: {payload['soak_json']}",
    f"- soak_elapsed_sec: {payload['soak_elapsed_sec']}",
    f"- soak_iteration_count: {payload['soak_iteration_count']}",
    f"- soak_processed_request_count: {payload['soak_processed_request_count']}",
    f"- soak_failed_job_count: {payload['soak_failed_job_count']}",
    f"- soak_avg_bpu_loading: {payload['soak_avg_bpu_loading']}",
    f"- soak_max_iteration_load_to_run_ratio: {payload['soak_max_iteration_load_to_run_ratio']}",
    f"- dry_run_json: {payload['dry_run_json']}",
    f"- dry_run_file_count: {payload['dry_run_file_count']}",
    f"- dry_run_upload_performed: {payload['dry_run_upload_performed']}",
    f"- service_plan: {payload['service_plan']}",
    f"- rollback_status: {payload['rollback_status']}",
    f"- default_service_replaced: {payload['default_service_replaced']}",
    "",
    "## Errors",
    "",
]
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
(run_dir / "long_running_candidate_acceptance_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "long_running_candidate_acceptance_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
