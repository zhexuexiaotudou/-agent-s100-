#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
min_processed_request_count="${DREAM7B_BPU_NORMAL_USE_MIN_PROCESSED_REQUEST_COUNT:-48}"
preferred_processed_request_count="${DREAM7B_BPU_NORMAL_USE_PREFERRED_PROCESSED_REQUEST_COUNT:-96}"
min_wall_delta_ratio="${DREAM7B_BPU_NORMAL_USE_MIN_WALL_DELTA_RATIO:-0.10}"
target_wall_ms_per_request="${DREAM7B_BPU_NORMAL_USE_TARGET_WALL_MS_PER_REQUEST:-1450}"
selected_pair_sustained_load_to_run_ratio="${DREAM7B_BPU_NORMAL_USE_SELECTED_PAIR_LOAD_TO_RUN_RATIO:-9.859028}"
best_load_to_run_ratio="${DREAM7B_BPU_NORMAL_USE_BEST_LOAD_TO_RUN_RATIO:-9.468172}"
min_avg_bpu_loading="${DREAM7B_BPU_NORMAL_USE_MIN_AVG_BPU_LOADING:-8.811}"
target_avg_bpu_loading="${DREAM7B_BPU_NORMAL_USE_TARGET_AVG_BPU_LOADING:-9.0}"
min_performance_pass_count="${DREAM7B_BPU_NORMAL_USE_MIN_PERFORMANCE_PASS_COUNT:-2}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

for item in "$min_processed_request_count" "$preferred_processed_request_count" "$min_performance_pass_count"; do
  if ! [[ "$item" =~ ^[1-9][0-9]*$ ]]; then
    echo "Normal-use integer thresholds must be positive integers." >&2
    exit 2
  fi
done
for item in "$min_wall_delta_ratio" "$target_wall_ms_per_request" "$selected_pair_sustained_load_to_run_ratio" "$best_load_to_run_ratio" "$min_avg_bpu_loading" "$target_avg_bpu_loading"; do
  if ! [[ "$item" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "Normal-use numeric thresholds must be non-negative numbers." >&2
    exit 2
  fi
done

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_normal_use_acceptance_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$report_root" \
  "$min_processed_request_count" \
  "$preferred_processed_request_count" \
  "$min_wall_delta_ratio" \
  "$target_wall_ms_per_request" \
  "$selected_pair_sustained_load_to_run_ratio" \
  "$best_load_to_run_ratio" \
  "$min_avg_bpu_loading" \
  "$target_avg_bpu_loading" \
  "$min_performance_pass_count" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
min_processed_request_count = int(sys.argv[3])
preferred_processed_request_count = int(sys.argv[4])
min_wall_delta_ratio = float(sys.argv[5])
target_wall_ms_per_request = float(sys.argv[6])
selected_pair_sustained_load_to_run_ratio = float(sys.argv[7])
best_load_to_run_ratio = float(sys.argv[8])
min_avg_bpu_loading = float(sys.argv[9])
target_avg_bpu_loading = float(sys.argv[10])
min_performance_pass_count = int(sys.argv[11])

warnings = []
evidence_gaps = []


def json_paths(pattern):
    paths = [Path(item) for item in glob.glob(str(report_root / pattern))]
    return sorted([item for item in paths if item.is_file()], key=lambda item: item.stat().st_mtime)


def latest_json(pattern):
    paths = json_paths(pattern)
    if not paths:
        return None, {}
    path = paths[-1]
    return path, json.loads(path.read_text(encoding="utf-8"))


def safe_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_ratio(numerator, denominator):
    numerator = safe_float(numerator)
    denominator = safe_float(denominator)
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def round_or_none(value, digits=6):
    value = safe_float(value)
    return round(value, digits) if value is not None else None


service_report_paths = json_paths("dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json")
service_reports = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in service_report_paths]
service_path, service = service_reports[-1] if service_reports else (None, {})
utilization_path, utilization = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
deployment_path, deployment = latest_json("dream7b_bpu_deployment_acceptance_*/deployment_acceptance_probe.json")
promotion_path, promotion = latest_json("dream7b_bpu_selected_pair_service_promotion_gate_*/selected_pair_service_promotion_gate_probe.json")
reload_path, reload = latest_json("dream7b_bpu_reload_optimization_*/reload_optimization_probe.json")
blocker_path, blocker = latest_json("dream7b_bpu_promotion_blocker_diagnosis_*/promotion_blocker_diagnosis_probe.json")
window_paths = json_paths("dream7b_bpu_resplit_window_cost_*/resplit_window_cost_probe.json")
latest_window_path = window_paths[-1] if window_paths else None
previous_window_path = window_paths[-2] if len(window_paths) >= 2 else None
latest_window = json.loads(latest_window_path.read_text(encoding="utf-8")) if latest_window_path else {}
previous_window = json.loads(previous_window_path.read_text(encoding="utf-8")) if previous_window_path else {}

required_reports = {
    "selected_pair_candidate_service_telemetry": service_path,
    "utilization_gap": utilization_path,
    "deployment_acceptance": deployment_path,
    "promotion_gate": promotion_path,
    "reload_optimization": reload_path,
    "promotion_blocker_diagnosis": blocker_path,
    "latest_window_cost": latest_window_path,
}
for name, path in required_reports.items():
    if not path:
        evidence_gaps.append(f"missing {name}")

processed_request_count = int(service.get("processed_request_count") or 0)
completed_job_count = int(service.get("completed_job_count") or 0)
failed_job_count = int(service.get("failed_job_count") or 0)
job_count = int(service.get("job_count") or 0)
batch_counts = service.get("batch_counts") or []
service_errors = service.get("errors") or []


def clean_service_report(data, min_count):
    report_batch_counts = data.get("batch_counts") or []
    report_job_count = int(data.get("job_count") or 0)
    return (
        data.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe"
        and data.get("service_name") == "dream7b-bpu-selected-pair-candidate.service"
        and int(data.get("processed_request_count") or 0) >= min_count
        and int(data.get("failed_job_count") or 0) == 0
        and int(data.get("completed_job_count") or 0) == report_job_count
        and isinstance(report_batch_counts, list)
        and all(int(item or 0) == 16 for item in report_batch_counts)
        and not data.get("errors")
    )


service_clean = clean_service_report(service, min_processed_request_count)
preferred_sustained_path = None
preferred_sustained_observed = False
for candidate_path, candidate in service_reports:
    if clean_service_report(candidate, preferred_processed_request_count):
        preferred_sustained_observed = True
        preferred_sustained_path = candidate_path

deployment_clean = (
    deployment.get("verdict") == "ok_dream7b_bpu_deployment_acceptance_probe"
    and deployment.get("check_count") == deployment.get("passed_check_count")
    and not deployment.get("errors")
)
promotion_rerun_clean = (
    promotion.get("verdict") == "ok_dream7b_bpu_selected_pair_service_promotion_gate_probe"
    and promotion.get("default_service_replaced") is False
    and isinstance(promotion.get("rollback_plan"), list)
    and any("restart dream7b-bpu-batch-queue.service" in item for item in promotion.get("rollback_plan", []))
)
candidate_isolated = (promotion.get("live_services") or {}).get("candidate_service_isolated_from_default") is True
deployable_rollback_safe = deployment_clean and promotion_rerun_clean and candidate_isolated

comparison = service.get("comparison_to_default_systemd_telemetry") or {}
reload_sustained = reload.get("sustained_service_candidate_metrics") or {}
wall_delta_vs_resplit = safe_float(
    reload_sustained.get("wall_delta_ratio_vs_resplit_per_request"),
    safe_float((promotion.get("metrics") or {}).get("wall_delta_ratio_vs_resplit_per_request")),
)
wall_delta_vs_default = safe_float(comparison.get("wall_ms_delta_ratio_vs_default_systemd"))
amortized_wall_ms = safe_float(service.get("amortized_wall_ms_per_processed_request"))
service_load_to_run_ratio = safe_float(service.get("load_to_run_ratio"), safe_ratio(service.get("total_load_ms"), service.get("total_run_ms")))
avg_bpu_loading = safe_float(service.get("avg_bpu_loading"))

performance_checks = [
    {
        "name": "wall_time_improved_vs_resplit_or_topwindow",
        "ok": wall_delta_vs_resplit is not None and wall_delta_vs_resplit >= min_wall_delta_ratio,
        "value": round_or_none(wall_delta_vs_resplit),
        "threshold": min_wall_delta_ratio,
    },
    {
        "name": "sustained_wall_ms_per_request_target",
        "ok": amortized_wall_ms is not None and amortized_wall_ms <= target_wall_ms_per_request,
        "value": round_or_none(amortized_wall_ms, 3),
        "threshold": target_wall_ms_per_request,
    },
    {
        "name": "load_to_run_ratio_improved_vs_selected_pair_sustained",
        "ok": service_load_to_run_ratio is not None and service_load_to_run_ratio < selected_pair_sustained_load_to_run_ratio,
        "value": round_or_none(service_load_to_run_ratio),
        "threshold": selected_pair_sustained_load_to_run_ratio,
        "preferred_threshold": best_load_to_run_ratio,
    },
    {
        "name": "avg_bpu_loading_not_below_topwindow",
        "ok": avg_bpu_loading is not None and avg_bpu_loading >= min_avg_bpu_loading,
        "value": round_or_none(avg_bpu_loading, 3),
        "threshold": min_avg_bpu_loading,
        "preferred_threshold": target_avg_bpu_loading,
    },
]
performance_pass_count = sum(1 for item in performance_checks if item["ok"])
performance_floor_met = performance_pass_count >= min_performance_pass_count

latest_top_ratio = latest_window.get("top_load_to_run_ratio_window") or {}
previous_top_ratio = previous_window.get("top_load_to_run_ratio_window") or {}
latest_top_load = latest_window.get("top_load_window") or {}
previous_top_load = previous_window.get("top_load_window") or {}
latest_overall_ratio = safe_float(latest_window.get("load_to_run_ratio"))
previous_overall_ratio = safe_float(previous_window.get("load_to_run_ratio"))
top_ratio_improved = (
    safe_float(latest_top_ratio.get("load_to_run_ratio")) is not None
    and safe_float(previous_top_ratio.get("load_to_run_ratio")) is not None
    and safe_float(latest_top_ratio.get("load_to_run_ratio")) < safe_float(previous_top_ratio.get("load_to_run_ratio"))
)
top_load_improved = (
    safe_float(latest_top_load.get("load_ms")) is not None
    and safe_float(previous_top_load.get("load_ms")) is not None
    and safe_float(latest_top_load.get("load_ms")) < safe_float(previous_top_load.get("load_ms"))
)
overall_load_to_run_improved = (
    latest_overall_ratio is not None
    and previous_overall_ratio is not None
    and latest_overall_ratio < previous_overall_ratio
)
post_blocker_window_cost_available = (
    latest_window_path is not None
    and blocker_path is not None
    and latest_window_path.stat().st_mtime > blocker_path.stat().st_mtime
)
reload_relief_observed = post_blocker_window_cost_available and (
    top_ratio_improved or top_load_improved or overall_load_to_run_improved
)
reload_blocker_reason = None
if not reload_relief_observed:
    max_resident = blocker.get("capacity_summary", {}).get("max_resident_segment_count_observed", blocker.get("max_resident_segment_count_observed"))
    seeded_quad = blocker.get("capacity_summary", {}).get("successful_seeded_quad_count", blocker.get("successful_seeded_quad_count"))
    if max_resident is not None or seeded_quad is not None:
        reload_blocker_reason = "resident_capacity_or_hbm_size_limit"
    elif not post_blocker_window_cost_available:
        reload_blocker_reason = "no_post_blocker_window_cost_experiment"
    else:
        reload_blocker_reason = "window_scheduling_did_not_reduce_reload_cost"

utilization_claim_compliant = (
    utilization.get("diagnosis") == "hbm_reload_dominated"
    or (performance_floor_met and reload_relief_observed)
)

requirements = {
    "stable_sustained_service": service_clean,
    "preferred_96_request_sustained_observed": preferred_sustained_observed,
    "deployment_acceptance_clean": deployment_clean,
    "performance_floor_met": performance_floor_met,
    "reload_relief_observed": reload_relief_observed,
    "deployable_rollback_safe": deployable_rollback_safe,
    "utilization_claim_compliant": utilization_claim_compliant,
}
normal_use_ready = (
    requirements["stable_sustained_service"]
    and requirements["deployment_acceptance_clean"]
    and requirements["performance_floor_met"]
    and requirements["reload_relief_observed"]
    and requirements["deployable_rollback_safe"]
    and requirements["utilization_claim_compliant"]
)

if service_clean and not preferred_sustained_observed:
    warnings.append("minimum sustained run passed, but preferred 96-request sustained evidence is not latest")
if wall_delta_vs_default is not None and wall_delta_vs_resplit is not None and wall_delta_vs_default >= min_wall_delta_ratio and wall_delta_vs_resplit < min_wall_delta_ratio:
    warnings.append("wall time improves versus default systemd but not versus the stricter resplit/top-window baseline")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_normal_use_acceptance_probe",
    "run_dir": str(run_dir),
    "report_root": str(report_root),
    "normal_use_ready": normal_use_ready,
    "normal_use_status": "ready" if normal_use_ready else "not_ready",
    "thresholds": {
        "min_processed_request_count": min_processed_request_count,
        "preferred_processed_request_count": preferred_processed_request_count,
        "min_wall_delta_ratio": min_wall_delta_ratio,
        "target_wall_ms_per_request": target_wall_ms_per_request,
        "selected_pair_sustained_load_to_run_ratio": selected_pair_sustained_load_to_run_ratio,
        "best_load_to_run_ratio": best_load_to_run_ratio,
        "min_avg_bpu_loading": min_avg_bpu_loading,
        "target_avg_bpu_loading": target_avg_bpu_loading,
        "min_performance_pass_count": min_performance_pass_count,
    },
    "requirements": requirements,
    "evidence_paths": {
        "selected_pair_candidate_service_telemetry": str(service_path) if service_path else "",
        "preferred_96_request_service_telemetry": str(preferred_sustained_path) if preferred_sustained_path else "",
        "utilization_gap": str(utilization_path) if utilization_path else "",
        "deployment_acceptance": str(deployment_path) if deployment_path else "",
        "promotion_gate": str(promotion_path) if promotion_path else "",
        "reload_optimization": str(reload_path) if reload_path else "",
        "promotion_blocker_diagnosis": str(blocker_path) if blocker_path else "",
        "latest_window_cost": str(latest_window_path) if latest_window_path else "",
        "previous_window_cost": str(previous_window_path) if previous_window_path else "",
    },
    "stability": {
        "service_clean": service_clean,
        "processed_request_count": processed_request_count,
        "preferred_sustained_observed": preferred_sustained_observed,
        "job_count": job_count,
        "completed_job_count": completed_job_count,
        "failed_job_count": failed_job_count,
        "batch_counts": batch_counts,
        "service_errors": service_errors,
    },
    "performance": {
        "performance_pass_count": performance_pass_count,
        "performance_floor_met": performance_floor_met,
        "wall_delta_ratio_vs_resplit_per_request": round_or_none(wall_delta_vs_resplit),
        "wall_delta_ratio_vs_default_systemd": round_or_none(wall_delta_vs_default),
        "amortized_wall_ms_per_processed_request": round_or_none(amortized_wall_ms, 3),
        "load_to_run_ratio": round_or_none(service_load_to_run_ratio),
        "avg_bpu_loading": round_or_none(avg_bpu_loading, 3),
        "max_bpu_loading": round_or_none(service.get("max_bpu_loading"), 3),
        "checks": performance_checks,
    },
    "reload_bottleneck": {
        "reload_relief_observed": reload_relief_observed,
        "post_blocker_window_cost_available": post_blocker_window_cost_available,
        "top_ratio_improved": top_ratio_improved,
        "top_load_improved": top_load_improved,
        "overall_load_to_run_improved": overall_load_to_run_improved,
        "reload_blocker_reason": reload_blocker_reason,
        "latest_top_load_to_run_ratio_window": latest_top_ratio,
        "previous_top_load_to_run_ratio_window": previous_top_ratio,
        "latest_top_load_window": latest_top_load,
        "previous_top_load_window": previous_top_load,
        "latest_overall_load_to_run_ratio": round_or_none(latest_overall_ratio),
        "previous_overall_load_to_run_ratio": round_or_none(previous_overall_ratio),
    },
    "deployment": {
        "deployment_clean": deployment_clean,
        "promotion_rerun_clean": promotion_rerun_clean,
        "candidate_isolated": candidate_isolated,
        "promotion_allowed": promotion.get("promotion_allowed"),
        "promotion_decision": promotion.get("promotion_decision"),
        "rollback_plan": promotion.get("rollback_plan"),
    },
    "utilization_statement": {
        "diagnosis": utilization.get("diagnosis"),
        "utilization_claim_compliant": utilization_claim_compliant,
        "max_bpu_loading_not_used_as_sole_success": True,
    },
    "evidence_gaps": evidence_gaps,
    "warnings": warnings,
    "unmet_requirements": [name for name, ok in requirements.items() if not ok],
}

(run_dir / "normal_use_acceptance_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Normal-Use Acceptance",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- normal_use_ready: {payload['normal_use_ready']}",
    f"- normal_use_status: {payload['normal_use_status']}",
    f"- processed_request_count: {processed_request_count}",
    f"- performance_pass_count: {performance_pass_count}/{min_performance_pass_count}",
    f"- reload_relief_observed: {reload_relief_observed}",
    f"- reload_blocker_reason: {reload_blocker_reason}",
    f"- deployment_clean: {deployment_clean}",
    f"- promotion_decision: {promotion.get('promotion_decision')}",
    "",
    "## Performance Checks",
    "",
]
for item in performance_checks:
    lines.append(f"- {item['name']}: ok={item['ok']}, value={item['value']}, threshold={item['threshold']}")
lines.extend(["", "## Unmet Requirements", ""])
if payload["unmet_requirements"]:
    lines.extend(f"- {item}" for item in payload["unmet_requirements"])
else:
    lines.append("- none")
lines.extend(["", "## Evidence Gaps", ""])
if evidence_gaps:
    lines.extend(f"- {item}" for item in evidence_gaps)
else:
    lines.append("- none")
(run_dir / "normal_use_acceptance_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "normal_use_acceptance_probe.md")
PY
