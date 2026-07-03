#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
min_processed_request_count="${DREAM7B_BPU_SELECTED_PAIR_SERVICE_PROMOTION_MIN_PROCESSED_REQUEST_COUNT:-48}"
min_sustained_round_count="${DREAM7B_BPU_SELECTED_PAIR_SERVICE_PROMOTION_MIN_ROUND_COUNT:-3}"
min_wall_delta_ratio="${DREAM7B_BPU_SELECTED_PAIR_SERVICE_PROMOTION_MIN_WALL_DELTA_RATIO:-0.05}"
min_avg_bpu_delta="${DREAM7B_BPU_SELECTED_PAIR_SERVICE_PROMOTION_MIN_AVG_BPU_DELTA:-0.0}"
max_load_to_run_ratio="${DREAM7B_BPU_SELECTED_PAIR_SERVICE_PROMOTION_MAX_LOAD_TO_RUN_RATIO:-9.468172}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$min_processed_request_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_SERVICE_PROMOTION_MIN_PROCESSED_REQUEST_COUNT must be a positive integer." >&2
  exit 2
fi
if ! [[ "$min_sustained_round_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_BPU_SELECTED_PAIR_SERVICE_PROMOTION_MIN_ROUND_COUNT must be a positive integer." >&2
  exit 2
fi
for item in "$min_wall_delta_ratio" "$min_avg_bpu_delta" "$max_load_to_run_ratio"; do
  if ! [[ "$item" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
    echo "Promotion numeric thresholds must be valid numbers." >&2
    exit 2
  fi
done

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_selected_pair_service_promotion_gate_$stamp"
mkdir -p "$run_dir"

default_service_status="$(systemctl is-active dream7b-bpu-batch-queue.service 2>/dev/null || true)"
default_service_enabled="$(systemctl is-enabled dream7b-bpu-batch-queue.service 2>/dev/null || true)"
candidate_service_status="$(systemctl is-active dream7b-bpu-selected-pair-candidate.service 2>/dev/null || true)"
candidate_service_enabled="$(systemctl is-enabled dream7b-bpu-selected-pair-candidate.service 2>/dev/null || true)"
default_exec_start="$(systemctl show dream7b-bpu-batch-queue.service -p ExecStart --value 2>/dev/null || true)"
candidate_exec_start="$(systemctl show dream7b-bpu-selected-pair-candidate.service -p ExecStart --value 2>/dev/null || true)"

python3 - \
  "$run_dir" \
  "$report_root" \
  "$min_processed_request_count" \
  "$min_sustained_round_count" \
  "$min_wall_delta_ratio" \
  "$min_avg_bpu_delta" \
  "$max_load_to_run_ratio" \
  "$default_service_status" \
  "$default_service_enabled" \
  "$candidate_service_status" \
  "$candidate_service_enabled" \
  "$default_exec_start" \
  "$candidate_exec_start" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
min_processed_request_count = int(sys.argv[3])
min_sustained_round_count = int(sys.argv[4])
min_wall_delta_ratio = float(sys.argv[5])
min_avg_bpu_delta = float(sys.argv[6])
max_load_to_run_ratio = float(sys.argv[7])
default_service_status = sys.argv[8]
default_service_enabled = sys.argv[9]
candidate_service_status = sys.argv[10]
candidate_service_enabled = sys.argv[11]
default_exec_start = sys.argv[12]
candidate_exec_start = sys.argv[13]

errors = []
warnings = []
checks = []
promotion_blockers = []


def latest_json(pattern):
    paths = [Path(item) for item in glob.glob(str(report_root / pattern))]
    paths = [item for item in paths if item.is_file()]
    if not paths:
        return None, {}
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def safe_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def add_check(name, ok, details, promotion_required=False):
    row = {
        "name": name,
        "ok": bool(ok),
        "promotion_required": bool(promotion_required),
        "details": details,
    }
    checks.append(row)
    if not ok:
        if promotion_required:
            promotion_blockers.append(name)
        else:
            errors.append(f"{name} failed: {details}")


service_path, service = latest_json("dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json")
utilization_path, utilization = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
acceptance_path, acceptance = latest_json("dream7b_bpu_deployment_acceptance_*/deployment_acceptance_probe.json")
reload_path, reload = latest_json("dream7b_bpu_reload_optimization_*/reload_optimization_probe.json")
selected_path, selected = latest_json("dream7b_bpu_selected_pair_telemetry_*/selected_pair_telemetry_probe.json")

comparison = service.get("comparison_to_default_systemd_telemetry") or {}
sustained = reload.get("sustained_service_candidate_metrics") or {}
current_resplit = reload.get("current_resplit_metrics") or {}
service_batch_counts = service.get("batch_counts")
service_batch_counts_valid = (
    isinstance(service_batch_counts, list)
    and len(service_batch_counts) >= min_sustained_round_count
    and all(int(item or 0) == 16 for item in service_batch_counts)
)

service_clean = (
    service.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe"
    and not service.get("errors")
    and service.get("service_name") == "dream7b-bpu-selected-pair-candidate.service"
    and int(service.get("processed_request_count") or 0) >= min_processed_request_count
    and service_batch_counts_valid
    and service.get("expected_window_execution_mode") == "selected-pair-resident"
    and service.get("expected_child_process_count") == 2
)
add_check(
    "sustained_selected_pair_service_telemetry_clean",
    service_clean,
    {
        "path": str(service_path) if service_path else "",
        "verdict": service.get("verdict"),
        "processed_request_count": service.get("processed_request_count"),
        "batch_counts": service_batch_counts,
        "batch_counts_valid": service_batch_counts_valid,
        "min_sustained_round_count": min_sustained_round_count,
        "expected_window_execution_mode": service.get("expected_window_execution_mode"),
        "expected_child_process_count": service.get("expected_child_process_count"),
        "errors": service.get("errors"),
    },
)

default_service_ok = (
    default_service_status == "active"
    and default_service_enabled == "enabled"
    and "/mnt/nas/openclaw/queues/dream7b-bpu " in f"{default_exec_start} "
    and "dream7b-bpu-selected-pair-batch-forward" not in default_exec_start
)
candidate_service_ok = (
    candidate_service_status == "active"
    and candidate_service_enabled == "enabled"
    and "/mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-candidate" in candidate_exec_start
    and "--forward-cmd dream7b-bpu-selected-pair-batch-forward" in candidate_exec_start
)
candidate_isolated = (
    "/mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-candidate" in candidate_exec_start
    and "/mnt/nas/openclaw/queues/dream7b-bpu " in f"{default_exec_start} "
    and "dream7b-bpu-selected-pair-batch-forward" not in default_exec_start
)
add_check(
    "live_default_service_health",
    default_service_ok,
    {
        "service_status": default_service_status,
        "service_enabled": default_service_enabled,
        "exec_start": default_exec_start,
    },
)
add_check(
    "live_candidate_service_health",
    candidate_service_ok,
    {
        "service_status": candidate_service_status,
        "service_enabled": candidate_service_enabled,
        "exec_start": candidate_exec_start,
    },
)
add_check(
    "candidate_service_isolated_from_default",
    candidate_isolated,
    {
        "default_exec_start": default_exec_start,
        "candidate_exec_start": candidate_exec_start,
    },
)

acceptance_ok = (
    acceptance.get("verdict") == "ok_dream7b_bpu_deployment_acceptance_probe"
    and acceptance.get("check_count") == acceptance.get("passed_check_count")
    and not acceptance.get("errors")
)
add_check(
    "deployment_acceptance_clean",
    acceptance_ok,
    {
        "path": str(acceptance_path) if acceptance_path else "",
        "verdict": acceptance.get("verdict"),
        "check_count": acceptance.get("check_count"),
        "passed_check_count": acceptance.get("passed_check_count"),
        "errors": acceptance.get("errors"),
    },
)

utilization_clean = (
    utilization.get("verdict") == "ok_dream7b_bpu_utilization_gap_probe"
    and not utilization.get("errors")
)
add_check(
    "utilization_gap_report_clean",
    utilization_clean,
    {
        "path": str(utilization_path) if utilization_path else "",
        "verdict": utilization.get("verdict"),
        "diagnosis": utilization.get("diagnosis"),
        "errors": utilization.get("errors"),
    },
)

reload_clean = (
    reload.get("verdict") == "ok_dream7b_bpu_reload_optimization_probe"
    and not reload.get("errors")
)
add_check(
    "reload_decision_report_clean",
    reload_clean,
    {
        "path": str(reload_path) if reload_path else "",
        "verdict": reload.get("verdict"),
        "final_decision": reload.get("final_decision"),
        "errors": reload.get("errors"),
    },
)

wall_delta_vs_default = safe_float(comparison.get("wall_ms_delta_ratio_vs_default_systemd"), 0.0)
wall_delta_vs_resplit = safe_float(sustained.get("wall_delta_ratio_vs_resplit_per_request"), 0.0)
avg_bpu_delta_vs_default = safe_float(comparison.get("avg_bpu_loading_delta_vs_default_systemd"), 0.0)
avg_bpu_delta_vs_resplit = safe_float(sustained.get("avg_bpu_delta_vs_resplit"), 0.0)
avg_bpu_delta_vs_single = safe_float(sustained.get("avg_bpu_delta_vs_selected_pair_single"), 0.0)
candidate_load_to_run_ratio = safe_float(sustained.get("load_to_run_ratio"), safe_float(service.get("load_to_run_ratio"), 0.0))

add_check(
    "promotion_wall_time_improved_vs_default",
    wall_delta_vs_default >= min_wall_delta_ratio,
    {
        "wall_delta_ratio_vs_default_systemd": wall_delta_vs_default,
        "min_wall_delta_ratio": min_wall_delta_ratio,
    },
    promotion_required=True,
)
add_check(
    "promotion_wall_time_improved_vs_resplit",
    wall_delta_vs_resplit >= min_wall_delta_ratio,
    {
        "wall_delta_ratio_vs_resplit_per_request": wall_delta_vs_resplit,
        "min_wall_delta_ratio": min_wall_delta_ratio,
    },
    promotion_required=True,
)
add_check(
    "promotion_average_bpu_not_worse_vs_default",
    comparison.get("candidate_avg_bpu_loading_not_worse_than_default_systemd") is True,
    {
        "candidate_avg_bpu_loading_not_worse_than_default_systemd": comparison.get("candidate_avg_bpu_loading_not_worse_than_default_systemd"),
        "avg_bpu_delta_vs_default_systemd": avg_bpu_delta_vs_default,
    },
    promotion_required=True,
)
add_check(
    "promotion_average_bpu_improved_vs_resplit",
    avg_bpu_delta_vs_resplit >= min_avg_bpu_delta,
    {
        "avg_bpu_delta_vs_resplit": avg_bpu_delta_vs_resplit,
        "min_avg_bpu_delta": min_avg_bpu_delta,
    },
    promotion_required=True,
)
add_check(
    "promotion_load_to_run_not_worse_than_best",
    candidate_load_to_run_ratio <= max_load_to_run_ratio,
    {
        "candidate_load_to_run_ratio": candidate_load_to_run_ratio,
        "max_load_to_run_ratio": max_load_to_run_ratio,
        "current_best_load_to_run_ratio": max_load_to_run_ratio,
    },
    promotion_required=True,
)
add_check(
    "promotion_not_hbm_reload_dominated",
    utilization.get("diagnosis") != "hbm_reload_dominated",
    {
        "diagnosis": utilization.get("diagnosis"),
    },
    promotion_required=True,
)
add_check(
    "reload_gate_allows_default_replacement",
    sustained.get("default_service_replacement_decision") != "do_not_replace_default_service_yet",
    {
        "final_decision": reload.get("final_decision"),
        "sustained_service_decision": sustained.get("sustained_service_decision"),
        "default_service_replacement_decision": sustained.get("default_service_replacement_decision"),
    },
    promotion_required=True,
)

promotion_allowed = not errors and not promotion_blockers
if promotion_allowed:
    promotion_decision = "allow_default_service_replacement_candidate"
    next_action = "Run an approved install/switch command, then immediately rerun sustained telemetry and deployment acceptance with rollback armed."
else:
    promotion_decision = "block_default_service_replacement"
    next_action = "Keep selected-pair as a candidate service only; optimize average BPU loading and load/run before any default-service replacement."

rollback_plan = [
    "sudo systemctl stop dream7b-bpu-selected-pair-candidate.service",
    "sudo systemctl disable dream7b-bpu-selected-pair-candidate.service",
    "sudo systemctl restart dream7b-bpu-batch-queue.service",
    "systemctl is-active dream7b-bpu-batch-queue.service",
    "systemctl is-enabled dream7b-bpu-batch-queue.service",
]

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_selected_pair_service_promotion_gate_probe" if not errors else "failed_dream7b_bpu_selected_pair_service_promotion_gate_probe",
    "run_dir": str(run_dir),
    "report_root": str(report_root),
    "min_processed_request_count": min_processed_request_count,
    "min_sustained_round_count": min_sustained_round_count,
    "min_wall_delta_ratio": min_wall_delta_ratio,
    "min_avg_bpu_delta": min_avg_bpu_delta,
    "max_load_to_run_ratio": max_load_to_run_ratio,
    "evidence_paths": {
        "selected_pair_telemetry": str(selected_path) if selected_path else "",
        "selected_pair_candidate_service_telemetry": str(service_path) if service_path else "",
        "utilization_gap": str(utilization_path) if utilization_path else "",
        "deployment_acceptance": str(acceptance_path) if acceptance_path else "",
        "reload_optimization": str(reload_path) if reload_path else "",
    },
    "live_services": {
        "default_service_status": default_service_status,
        "default_service_enabled": default_service_enabled,
        "candidate_service_status": candidate_service_status,
        "candidate_service_enabled": candidate_service_enabled,
        "candidate_service_isolated_from_default": candidate_isolated,
    },
    "metrics": {
        "processed_request_count": service.get("processed_request_count"),
        "batch_counts": service_batch_counts,
        "batch_counts_valid": service_batch_counts_valid,
        "amortized_wall_ms_per_processed_request": service.get("amortized_wall_ms_per_processed_request"),
        "avg_bpu_loading": service.get("avg_bpu_loading"),
        "max_bpu_loading": service.get("max_bpu_loading"),
        "candidate_load_to_run_ratio": candidate_load_to_run_ratio,
        "wall_delta_ratio_vs_default_systemd": wall_delta_vs_default,
        "wall_delta_ratio_vs_resplit_per_request": wall_delta_vs_resplit,
        "avg_bpu_delta_vs_default_systemd": avg_bpu_delta_vs_default,
        "avg_bpu_delta_vs_resplit": avg_bpu_delta_vs_resplit,
        "avg_bpu_delta_vs_selected_pair_single": avg_bpu_delta_vs_single,
        "utilization_diagnosis": utilization.get("diagnosis"),
        "reload_final_decision": reload.get("final_decision"),
        "sustained_service_decision": sustained.get("sustained_service_decision"),
        "default_service_replacement_decision": sustained.get("default_service_replacement_decision"),
    },
    "promotion_allowed": promotion_allowed,
    "promotion_decision": promotion_decision,
    "promotion_blockers": promotion_blockers,
    "default_service_replaced": False,
    "rollback_plan": rollback_plan,
    "next_action": next_action,
    "checks": checks,
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "selected_pair_service_promotion_gate_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Selected-Pair Service Promotion Gate",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- promotion_allowed: {payload['promotion_allowed']}",
    f"- promotion_decision: {payload['promotion_decision']}",
    f"- default_service_replaced: {payload['default_service_replaced']}",
    f"- next_action: {payload['next_action']}",
    "",
    "## Key Metrics",
    "",
]
for key, value in payload["metrics"].items():
    lines.append(f"- {key}: {value}")
lines.extend(["", "## Promotion Blockers", ""])
lines.extend(f"- {item}" for item in promotion_blockers) if promotion_blockers else lines.append("- none")
lines.extend(["", "## Rollback Plan", ""])
lines.extend(f"- `{item}`" for item in rollback_plan)
lines.extend(["", "## Checks", ""])
for check in checks:
    lines.append(f"- {check['name']}: ok={check['ok']} promotion_required={check['promotion_required']}")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "selected_pair_service_promotion_gate_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "selected_pair_service_promotion_gate_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
