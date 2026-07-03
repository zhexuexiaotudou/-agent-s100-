#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
min_processed_request_count="${DREAM7B_BPU_CROSS_JOB_SERVICE_PROMOTION_MIN_PROCESSED_REQUEST_COUNT:-192}"
max_load_to_run_ratio="${DREAM7B_BPU_CROSS_JOB_SERVICE_PROMOTION_MAX_LOAD_TO_RUN_RATIO:-9.443895}"
min_avg_bpu_loading="${DREAM7B_BPU_CROSS_JOB_SERVICE_PROMOTION_MIN_AVG_BPU_LOADING:-8.811}"
max_wall_ms_per_request="${DREAM7B_BPU_CROSS_JOB_SERVICE_PROMOTION_MAX_WALL_MS_PER_REQUEST:-1451.906}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_selected_pair_cross_job_service_promotion_gate_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$report_root" \
  "$min_processed_request_count" \
  "$max_load_to_run_ratio" \
  "$min_avg_bpu_loading" \
  "$max_wall_ms_per_request" <<'PY'
import glob
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
min_processed_request_count = int(sys.argv[3])
max_load_to_run_ratio = float(sys.argv[4])
min_avg_bpu_loading = float(sys.argv[5])
max_wall_ms_per_request = float(sys.argv[6])


def latest_json(pattern):
    paths = [Path(item) for item in glob.glob(str(report_root / pattern))]
    paths = [item for item in paths if item.is_file()]
    if not paths:
        return None, {}
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def systemctl_value(*args):
    proc = subprocess.run(["systemctl", *args], text=True, capture_output=True)
    return proc.stdout.strip() if proc.returncode == 0 else (proc.stdout + proc.stderr).strip()


telemetry_path, telemetry = latest_json(
    "dream7b_bpu_selected_pair_cross_job_candidate_service_telemetry_*/service_telemetry_probe.json"
)
fallback_path, fallback = latest_json(
    "dream7b_bpu_selected_pair_cross_job_service_fallback_*/cross_job_service_fallback_probe.json"
)
default_promotion_path, default_promotion = latest_json(
    "dream7b_bpu_cross_job_default_promotion_*/cross_job_default_promotion_probe.json"
)
deployment_path, deployment = latest_json("dream7b_bpu_deployment_acceptance_*/deployment_acceptance_probe.json")

service_name = "dream7b-bpu-selected-pair-cross-job-candidate.service"
default_service_name = "dream7b-bpu-batch-queue.service"
service_status = systemctl_value("is-active", service_name)
service_enabled = systemctl_value("is-enabled", service_name)
default_status = systemctl_value("is-active", default_service_name)
default_enabled = systemctl_value("is-enabled", default_service_name)
unit_path = systemctl_value("show", service_name, "-p", "FragmentPath", "--value")
exec_start = systemctl_value("show", service_name, "-p", "ExecStart", "--value")
default_exec_start = systemctl_value("show", default_service_name, "-p", "ExecStart", "--value")
default_service_replaced = (
    "dream7b_bpu_selected_pair_cross_job_queue_service.py" in default_exec_start
    and "/mnt/nas/openclaw/queues/dream7b-bpu" in default_exec_start
    and "--single-job-flush-timeout-sec" in default_exec_start
)
rollback_verified = default_promotion.get("rollback_verified") is True

checks = []


def add_check(name, ok, value=None, threshold=None):
    checks.append({"name": name, "ok": bool(ok), "value": value, "threshold": threshold})


processed = int(telemetry.get("processed_request_count") or 0)
failed = int(telemetry.get("failed_job_count") or 0)
load_to_run = telemetry.get("load_to_run_ratio")
avg_bpu = telemetry.get("avg_bpu_loading")
wall = telemetry.get("amortized_wall_ms_per_processed_request")

add_check("telemetry_verdict_ok", telemetry.get("verdict") == "ok_dream7b_bpu_selected_pair_cross_job_candidate_service_telemetry_probe", telemetry.get("verdict"))
add_check("processed_request_count_ge_min", processed >= min_processed_request_count, processed, min_processed_request_count)
add_check("failed_job_count_zero", failed == 0, failed, 0)
add_check("load_to_run_below_threshold", load_to_run is not None and float(load_to_run) < max_load_to_run_ratio, load_to_run, max_load_to_run_ratio)
add_check("avg_bpu_loading_ge_threshold", avg_bpu is not None and float(avg_bpu) >= min_avg_bpu_loading, avg_bpu, min_avg_bpu_loading)
add_check("wall_not_degraded_vs_long_sustained", wall is not None and float(wall) <= max_wall_ms_per_request, wall, max_wall_ms_per_request)
add_check("service_active", service_status == "active", service_status)
add_check("service_enabled", service_enabled == "enabled", service_enabled)
add_check("default_service_still_active", default_status == "active", default_status)
add_check("default_service_still_enabled", default_enabled == "enabled", default_enabled)
add_check("candidate_service_isolated", service_name in unit_path and default_service_name not in unit_path, unit_path)
add_check("execstart_uses_cross_job_service", "dream7b_bpu_selected_pair_cross_job_queue_service.py" in exec_start, exec_start)
add_check("execstart_enables_single_job_flush", "--single-job-flush-timeout-sec" in exec_start, exec_start)
add_check(
    "default_promoted_execstart_valid_when_replaced",
    (not default_service_replaced)
    or (
        "dream7b_bpu_selected_pair_cross_job_queue_service.py" in default_exec_start
        and "/mnt/nas/openclaw/queues/dream7b-bpu" in default_exec_start
        and "--single-job-flush-timeout-sec" in default_exec_start
    ),
    default_exec_start,
)
add_check("rollback_verified_after_replacement", (not default_service_replaced) or rollback_verified, rollback_verified)
add_check(
    "single_job_fallback_ok",
    fallback.get("verdict") == "ok_dream7b_bpu_selected_pair_cross_job_service_fallback_probe"
    and fallback.get("single_job_fallback_ok") is True
    and fallback.get("processed_job_count") == 1
    and fallback.get("failed_job_count") == 0,
    fallback.get("verdict"),
)
add_check("deployment_acceptance_clean", deployment.get("verdict") == "ok_dream7b_bpu_deployment_acceptance_probe" and deployment.get("errors") == [], deployment.get("verdict"))

promotion_allowed = all(item["ok"] for item in checks)
promotion_blockers = [item["name"] for item in checks if not item["ok"]]
rollback_plan = [
    f"sudo systemctl stop {service_name}",
    f"sudo systemctl disable {service_name}",
    f"sudo systemctl restart {default_service_name}",
    f"systemctl is-active {default_service_name}",
    f"systemctl is-enabled {default_service_name}",
]

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_selected_pair_cross_job_service_promotion_gate_probe",
    "run_dir": str(run_dir),
    "promotion_allowed": promotion_allowed,
    "promotion_decision": "ready_for_default_service_replacement" if promotion_allowed else "block_default_service_replacement",
    "default_service_replaced": default_service_replaced,
    "rollback_verified": rollback_verified,
    "candidate_service_isolated_from_default": True,
    "service_name": service_name,
    "default_service_name": default_service_name,
    "telemetry_path": str(telemetry_path) if telemetry_path else "",
    "single_job_fallback_path": str(fallback_path) if fallback_path else "",
    "default_promotion_path": str(default_promotion_path) if default_promotion_path else "",
    "deployment_acceptance_path": str(deployment_path) if deployment_path else "",
    "processed_request_count": processed,
    "failed_job_count": failed,
    "load_to_run_ratio": load_to_run,
    "avg_bpu_loading": avg_bpu,
    "amortized_wall_ms_per_processed_request": wall,
    "service_status": service_status,
    "service_enabled": service_enabled,
    "default_status": default_status,
    "default_enabled": default_enabled,
    "unit_path": unit_path,
    "exec_start": exec_start,
    "default_exec_start": default_exec_start,
    "single_job_fallback": {
        "verdict": fallback.get("verdict"),
        "single_job_fallback_ok": fallback.get("single_job_fallback_ok"),
        "run_reason": fallback.get("run_reason"),
        "processed_job_count": fallback.get("processed_job_count"),
        "processed_request_count": fallback.get("processed_request_count"),
        "failed_job_count": fallback.get("failed_job_count"),
    },
    "checks": checks,
    "promotion_blockers": promotion_blockers,
    "rollback_plan": rollback_plan,
    "errors": [],
}
(run_dir / "cross_job_service_promotion_gate_probe.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
lines = [
    "# Dream 7B Cross-Job Service Promotion Gate",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- promotion_allowed: {payload['promotion_allowed']}",
    f"- promotion_decision: {payload['promotion_decision']}",
    f"- default_service_replaced: {payload['default_service_replaced']}",
    f"- rollback_verified: {payload['rollback_verified']}",
    f"- processed_request_count: {payload['processed_request_count']}",
    f"- load_to_run_ratio: {payload['load_to_run_ratio']}",
    f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
    f"- amortized_wall_ms_per_processed_request: {payload['amortized_wall_ms_per_processed_request']}",
    f"- single_job_fallback_ok: {payload['single_job_fallback']['single_job_fallback_ok']}",
    "",
    "## Promotion Blockers",
    "",
]
lines.extend(f"- {item}" for item in promotion_blockers) if promotion_blockers else lines.append("- none")
(run_dir / "cross_job_service_promotion_gate_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "cross_job_service_promotion_gate_probe.md")
PY
