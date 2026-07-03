#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
min_processed_request_count="${DREAM7B_BPU_DEFAULT_DEPLOY_MIN_PROCESSED_REQUEST_COUNT:-96}"
preferred_processed_request_count="${DREAM7B_BPU_DEFAULT_DEPLOY_PREFERRED_PROCESSED_REQUEST_COUNT:-192}"
target_wall_ms_per_request="${DREAM7B_BPU_DEFAULT_DEPLOY_TARGET_WALL_MS_PER_REQUEST:-1400}"
max_load_to_run_ratio="${DREAM7B_BPU_DEFAULT_DEPLOY_MAX_LOAD_TO_RUN_RATIO:-9.443895}"
target_load_to_run_ratio="${DREAM7B_BPU_DEFAULT_DEPLOY_TARGET_LOAD_TO_RUN_RATIO:-9.0}"
min_avg_bpu_loading="${DREAM7B_BPU_DEFAULT_DEPLOY_MIN_AVG_BPU_LOADING:-8.811}"
target_avg_bpu_loading="${DREAM7B_BPU_DEFAULT_DEPLOY_TARGET_AVG_BPU_LOADING:-9.0}"
normal_use_wall_ms="${DREAM7B_BPU_DEFAULT_DEPLOY_NORMAL_USE_WALL_MS:-1448.877}"
long_sustained_wall_ms="${DREAM7B_BPU_DEFAULT_DEPLOY_LONG_SUSTAINED_WALL_MS:-1451.906}"
min_wall_delta_ratio="${DREAM7B_BPU_DEFAULT_DEPLOY_MIN_WALL_DELTA_RATIO:-0.05}"
min_performance_pass_count="${DREAM7B_BPU_DEFAULT_DEPLOY_MIN_PERFORMANCE_PASS_COUNT:-3}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

for item in "$min_processed_request_count" "$preferred_processed_request_count" "$min_performance_pass_count"; do
  if ! [[ "$item" =~ ^[1-9][0-9]*$ ]]; then
    echo "Default-deploy integer thresholds must be positive integers." >&2
    exit 2
  fi
done
for item in "$target_wall_ms_per_request" "$max_load_to_run_ratio" "$target_load_to_run_ratio" "$min_avg_bpu_loading" "$target_avg_bpu_loading" "$normal_use_wall_ms" "$long_sustained_wall_ms" "$min_wall_delta_ratio"; do
  if ! [[ "$item" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "Default-deploy numeric thresholds must be non-negative numbers." >&2
    exit 2
  fi
done

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_default_deployable_acceptance_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$report_root" \
  "$min_processed_request_count" \
  "$preferred_processed_request_count" \
  "$target_wall_ms_per_request" \
  "$max_load_to_run_ratio" \
  "$target_load_to_run_ratio" \
  "$min_avg_bpu_loading" \
  "$target_avg_bpu_loading" \
  "$normal_use_wall_ms" \
  "$long_sustained_wall_ms" \
  "$min_wall_delta_ratio" \
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
target_wall_ms_per_request = float(sys.argv[5])
max_load_to_run_ratio = float(sys.argv[6])
target_load_to_run_ratio = float(sys.argv[7])
min_avg_bpu_loading = float(sys.argv[8])
target_avg_bpu_loading = float(sys.argv[9])
normal_use_wall_ms = float(sys.argv[10])
long_sustained_wall_ms = float(sys.argv[11])
min_wall_delta_ratio = float(sys.argv[12])
min_performance_pass_count = int(sys.argv[13])

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


def ratio(numerator, denominator):
    numerator = safe_float(numerator)
    denominator = safe_float(denominator)
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def round_or_none(value, digits=6):
    value = safe_float(value)
    return round(value, digits) if value is not None else None


service_path, service = latest_json("dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json")
cross_job_path, cross_job = latest_json("dream7b_bpu_selected_pair_cross_job_reuse_*/selected_pair_cross_job_reuse_probe.json")
cross_queue_path, cross_queue = latest_json("dream7b_bpu_selected_pair_cross_job_queue_runner_*/cross_job_queue_summary.json")
cross_service_telemetry_path, cross_service_telemetry = latest_json("dream7b_bpu_selected_pair_cross_job_candidate_service_telemetry_*/service_telemetry_probe.json")
cross_service_promotion_path, cross_service_promotion = latest_json("dream7b_bpu_selected_pair_cross_job_service_promotion_gate_*/cross_job_service_promotion_gate_probe.json")
cross_default_telemetry_path, cross_default_telemetry = latest_json("dream7b_bpu_cross_job_default_service_telemetry_*/default_service_telemetry_probe.json")
deployment_path, deployment = latest_json("dream7b_bpu_deployment_acceptance_*/deployment_acceptance_probe.json")
promotion_path, promotion = latest_json("dream7b_bpu_selected_pair_service_promotion_gate_*/selected_pair_service_promotion_gate_probe.json")
reload_path, reload = latest_json("dream7b_bpu_reload_optimization_*/reload_optimization_probe.json")
utilization_path, utilization = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
window_paths = json_paths("dream7b_bpu_resplit_window_cost_*/resplit_window_cost_probe.json")
latest_window_path = window_paths[-1] if window_paths else None
previous_window_path = window_paths[-2] if len(window_paths) >= 2 else None
latest_window = json.loads(latest_window_path.read_text(encoding="utf-8")) if latest_window_path else {}
previous_window = json.loads(previous_window_path.read_text(encoding="utf-8")) if previous_window_path else {}

for name, path in {
    "selected_pair_candidate_service_telemetry": service_path,
    "selected_pair_cross_job_reuse": cross_job_path,
    "selected_pair_cross_job_queue_runner": cross_queue_path,
    "selected_pair_cross_job_candidate_service_telemetry": cross_service_telemetry_path,
    "selected_pair_cross_job_service_promotion_gate": cross_service_promotion_path,
    "cross_job_default_service_telemetry": cross_default_telemetry_path,
    "deployment_acceptance": deployment_path,
    "promotion_gate": promotion_path,
    "reload_optimization": reload_path,
    "utilization_gap": utilization_path,
    "latest_window_cost": latest_window_path,
}.items():
    if not path:
        evidence_gaps.append(f"missing {name}")

batch_counts = service.get("batch_counts") or []
processed_request_count = int(service.get("processed_request_count") or 0)
job_count = int(service.get("job_count") or 0)
completed_job_count = int(service.get("completed_job_count") or 0)
failed_job_count = int(service.get("failed_job_count") or 0)
service_clean = (
    service.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe"
    and service.get("service_name") == "dream7b-bpu-selected-pair-candidate.service"
    and processed_request_count >= min_processed_request_count
    and completed_job_count == job_count
    and failed_job_count == 0
    and isinstance(batch_counts, list)
    and all(int(item or 0) == 16 for item in batch_counts)
    and not service.get("errors")
)
preferred_sustained_observed = processed_request_count >= preferred_processed_request_count

service_wall_ms = safe_float(service.get("amortized_wall_ms_per_processed_request"))
service_load_to_run = safe_float(service.get("load_to_run_ratio"), ratio(service.get("total_load_ms"), service.get("total_run_ms")))
service_avg_bpu = safe_float(service.get("avg_bpu_loading"))
wall_delta_vs_normal_use = (
    (normal_use_wall_ms - service_wall_ms) / normal_use_wall_ms
    if service_wall_ms is not None and normal_use_wall_ms
    else None
)
long_sustained_not_degraded = service_wall_ms is not None and service_wall_ms <= long_sustained_wall_ms

service_performance_checks = [
    {
        "name": "service_wall_ms_per_request_le_1400",
        "ok": service_wall_ms is not None and service_wall_ms <= target_wall_ms_per_request,
        "value": round_or_none(service_wall_ms, 3),
        "threshold": target_wall_ms_per_request,
    },
    {
        "name": "service_load_to_run_below_latest_window",
        "ok": service_load_to_run is not None and service_load_to_run < max_load_to_run_ratio,
        "value": round_or_none(service_load_to_run),
        "threshold": max_load_to_run_ratio,
        "preferred_threshold": target_load_to_run_ratio,
    },
    {
        "name": "service_avg_bpu_not_below_topwindow",
        "ok": service_avg_bpu is not None and service_avg_bpu >= min_avg_bpu_loading,
        "value": round_or_none(service_avg_bpu, 3),
        "threshold": min_avg_bpu_loading,
        "preferred_threshold": target_avg_bpu_loading,
    },
    {
        "name": "service_wall_improves_5pct_vs_normal_use",
        "ok": wall_delta_vs_normal_use is not None and wall_delta_vs_normal_use >= min_wall_delta_ratio,
        "value": round_or_none(wall_delta_vs_normal_use),
        "threshold": min_wall_delta_ratio,
    },
    {
        "name": "service_long_sustained_not_degraded",
        "ok": long_sustained_not_degraded,
        "value": round_or_none(service_wall_ms, 3),
        "threshold": long_sustained_wall_ms,
    },
]
service_performance_pass_count = sum(1 for item in service_performance_checks if item["ok"])
service_performance_floor_met = service_performance_pass_count >= min_performance_pass_count

cross_metrics = cross_job.get("cross_job_metrics") or {}
cross_comparison = cross_job.get("comparison_to_selected_pair_candidate_service") or {}
cross_wall = safe_float(cross_metrics.get("amortized_wall_ms_per_forward"))
cross_load_to_run = ratio(cross_metrics.get("selected_total_load_ms"), cross_metrics.get("run_ms"))
cross_long_not_degraded = cross_wall is not None and cross_wall <= long_sustained_wall_ms
cross_wall_delta_vs_normal_use = (
    (normal_use_wall_ms - cross_wall) / normal_use_wall_ms
    if cross_wall is not None and normal_use_wall_ms
    else None
)
cross_job_prototype = (
    cross_job.get("verdict") == "ok_dream7b_bpu_selected_pair_cross_job_reuse_probe"
    and int(cross_job.get("processed_forward_count") or 0) >= min_processed_request_count
    and cross_job.get("selected_pair") == [1, 8]
    and cross_job.get("selected_pair_covers_all_segments") is True
    and cross_comparison.get("cross_job_load_time_improved") is True
    and not cross_job.get("errors")
)
cross_performance_checks = [
    {
        "name": "cross_job_wall_ms_per_forward_le_1400",
        "ok": cross_wall is not None and cross_wall <= target_wall_ms_per_request,
        "value": round_or_none(cross_wall, 3),
        "threshold": target_wall_ms_per_request,
    },
    {
        "name": "cross_job_load_to_run_below_latest_window",
        "ok": cross_load_to_run is not None and cross_load_to_run < max_load_to_run_ratio,
        "value": round_or_none(cross_load_to_run),
        "threshold": max_load_to_run_ratio,
        "preferred_threshold": target_load_to_run_ratio,
    },
    {
        "name": "cross_job_wall_improves_5pct_vs_normal_use",
        "ok": cross_wall_delta_vs_normal_use is not None and cross_wall_delta_vs_normal_use >= min_wall_delta_ratio,
        "value": round_or_none(cross_wall_delta_vs_normal_use),
        "threshold": min_wall_delta_ratio,
    },
    {
        "name": "cross_job_long_sustained_not_degraded",
        "ok": cross_long_not_degraded,
        "value": round_or_none(cross_wall, 3),
        "threshold": long_sustained_wall_ms,
    },
]
cross_performance_pass_count = sum(1 for item in cross_performance_checks if item["ok"])

cross_queue_wall = safe_float(cross_queue.get("amortized_wall_ms_per_processed_request"))
cross_queue_load_to_run = safe_float(cross_queue.get("load_to_run_ratio"))
cross_queue_processed = int(cross_queue.get("processed_request_count") or 0)
cross_queue_failed_jobs = int(cross_queue.get("failed_job_count") or 0)
cross_queue_long_not_degraded = cross_queue_wall is not None and cross_queue_wall <= long_sustained_wall_ms
cross_queue_wall_delta_vs_normal_use = (
    (normal_use_wall_ms - cross_queue_wall) / normal_use_wall_ms
    if cross_queue_wall is not None and normal_use_wall_ms
    else None
)
cross_queue_candidate = (
    cross_queue.get("verdict") == "ok_dream7b_bpu_selected_pair_cross_job_queue_runner"
    and cross_queue_processed >= min_processed_request_count
    and cross_queue_failed_jobs == 0
    and cross_queue.get("selected_pair") == [1, 8]
    and cross_queue.get("selected_pair_covers_all_segments") is True
    and not cross_queue.get("errors")
)
cross_queue_preferred_observed = cross_queue_processed >= preferred_processed_request_count
cross_queue_performance_checks = [
    {
        "name": "cross_job_queue_wall_ms_per_request_le_1400",
        "ok": cross_queue_wall is not None and cross_queue_wall <= target_wall_ms_per_request,
        "value": round_or_none(cross_queue_wall, 3),
        "threshold": target_wall_ms_per_request,
    },
    {
        "name": "cross_job_queue_load_to_run_below_latest_window",
        "ok": cross_queue_load_to_run is not None and cross_queue_load_to_run < max_load_to_run_ratio,
        "value": round_or_none(cross_queue_load_to_run),
        "threshold": max_load_to_run_ratio,
        "preferred_threshold": target_load_to_run_ratio,
    },
    {
        "name": "cross_job_queue_wall_improves_5pct_vs_normal_use",
        "ok": cross_queue_wall_delta_vs_normal_use is not None and cross_queue_wall_delta_vs_normal_use >= min_wall_delta_ratio,
        "value": round_or_none(cross_queue_wall_delta_vs_normal_use),
        "threshold": min_wall_delta_ratio,
    },
    {
        "name": "cross_job_queue_long_sustained_not_degraded",
        "ok": cross_queue_long_not_degraded,
        "value": round_or_none(cross_queue_wall, 3),
        "threshold": long_sustained_wall_ms,
    },
]
cross_queue_performance_pass_count = sum(1 for item in cross_queue_performance_checks if item["ok"])

cross_service_wall = safe_float(cross_service_telemetry.get("amortized_wall_ms_per_processed_request"))
cross_service_load_to_run = safe_float(cross_service_telemetry.get("load_to_run_ratio"))
cross_service_avg_bpu = safe_float(cross_service_telemetry.get("avg_bpu_loading"))
cross_service_processed = int(cross_service_telemetry.get("processed_request_count") or 0)
cross_service_failed_jobs = int(cross_service_telemetry.get("failed_job_count") or 0)
cross_service_long_not_degraded = cross_service_wall is not None and cross_service_wall <= long_sustained_wall_ms
cross_service_wall_delta_vs_normal_use = (
    (normal_use_wall_ms - cross_service_wall) / normal_use_wall_ms
    if cross_service_wall is not None and normal_use_wall_ms
    else None
)
cross_service_clean = (
    cross_service_telemetry.get("verdict") == "ok_dream7b_bpu_selected_pair_cross_job_candidate_service_telemetry_probe"
    and cross_service_telemetry.get("service_name") == "dream7b-bpu-selected-pair-cross-job-candidate.service"
    and cross_service_processed >= min_processed_request_count
    and cross_service_failed_jobs == 0
    and cross_service_telemetry.get("selected_pair") == [1, 8]
    and cross_service_telemetry.get("selected_pair_covers_all_segments") is True
    and not cross_service_telemetry.get("errors")
)
cross_service_preferred_observed = cross_service_processed >= preferred_processed_request_count
cross_service_performance_checks = [
    {
        "name": "cross_job_service_wall_ms_per_request_le_1400",
        "ok": cross_service_wall is not None and cross_service_wall <= target_wall_ms_per_request,
        "value": round_or_none(cross_service_wall, 3),
        "threshold": target_wall_ms_per_request,
    },
    {
        "name": "cross_job_service_load_to_run_below_latest_window",
        "ok": cross_service_load_to_run is not None and cross_service_load_to_run < max_load_to_run_ratio,
        "value": round_or_none(cross_service_load_to_run),
        "threshold": max_load_to_run_ratio,
        "preferred_threshold": target_load_to_run_ratio,
    },
    {
        "name": "cross_job_service_avg_bpu_not_below_topwindow",
        "ok": cross_service_avg_bpu is not None and cross_service_avg_bpu >= min_avg_bpu_loading,
        "value": round_or_none(cross_service_avg_bpu, 3),
        "threshold": min_avg_bpu_loading,
        "preferred_threshold": target_avg_bpu_loading,
    },
    {
        "name": "cross_job_service_wall_improves_5pct_vs_normal_use",
        "ok": cross_service_wall_delta_vs_normal_use is not None and cross_service_wall_delta_vs_normal_use >= min_wall_delta_ratio,
        "value": round_or_none(cross_service_wall_delta_vs_normal_use),
        "threshold": min_wall_delta_ratio,
    },
    {
        "name": "cross_job_service_long_sustained_not_degraded",
        "ok": cross_service_long_not_degraded,
        "value": round_or_none(cross_service_wall, 3),
        "threshold": long_sustained_wall_ms,
    },
]
cross_service_performance_pass_count = sum(1 for item in cross_service_performance_checks if item["ok"])
cross_service_promotion_allowed = cross_service_promotion.get("promotion_allowed") is True

cross_default_wall = safe_float(cross_default_telemetry.get("amortized_wall_ms_per_processed_request"))
cross_default_load_to_run = safe_float(cross_default_telemetry.get("load_to_run_ratio"))
cross_default_avg_bpu = safe_float(cross_default_telemetry.get("avg_bpu_loading"))
cross_default_processed = int(cross_default_telemetry.get("processed_request_count") or 0)
cross_default_failed_jobs = int(cross_default_telemetry.get("failed_job_count") or 0)
cross_default_long_not_degraded = cross_default_wall is not None and cross_default_wall <= long_sustained_wall_ms
cross_default_wall_delta_vs_normal_use = (
    (normal_use_wall_ms - cross_default_wall) / normal_use_wall_ms
    if cross_default_wall is not None and normal_use_wall_ms
    else None
)
cross_default_clean = (
    cross_default_telemetry.get("verdict") == "ok_dream7b_bpu_cross_job_default_service_telemetry_probe"
    and cross_default_telemetry.get("service_name") == "dream7b-bpu-batch-queue.service"
    and cross_default_processed >= min_processed_request_count
    and cross_default_failed_jobs == 0
    and cross_default_telemetry.get("selected_pair") == [1, 8]
    and cross_default_telemetry.get("selected_pair_covers_all_segments") is True
    and not cross_default_telemetry.get("errors")
)
cross_default_preferred_observed = cross_default_processed >= preferred_processed_request_count
cross_default_performance_checks = [
    {
        "name": "cross_job_default_wall_ms_per_request_le_1400",
        "ok": cross_default_wall is not None and cross_default_wall <= target_wall_ms_per_request,
        "value": round_or_none(cross_default_wall, 3),
        "threshold": target_wall_ms_per_request,
    },
    {
        "name": "cross_job_default_load_to_run_below_latest_window",
        "ok": cross_default_load_to_run is not None and cross_default_load_to_run < max_load_to_run_ratio,
        "value": round_or_none(cross_default_load_to_run),
        "threshold": max_load_to_run_ratio,
        "preferred_threshold": target_load_to_run_ratio,
    },
    {
        "name": "cross_job_default_avg_bpu_not_below_topwindow",
        "ok": cross_default_avg_bpu is not None and cross_default_avg_bpu >= min_avg_bpu_loading,
        "value": round_or_none(cross_default_avg_bpu, 3),
        "threshold": min_avg_bpu_loading,
        "preferred_threshold": target_avg_bpu_loading,
    },
    {
        "name": "cross_job_default_wall_improves_5pct_vs_normal_use",
        "ok": cross_default_wall_delta_vs_normal_use is not None and cross_default_wall_delta_vs_normal_use >= min_wall_delta_ratio,
        "value": round_or_none(cross_default_wall_delta_vs_normal_use),
        "threshold": min_wall_delta_ratio,
    },
    {
        "name": "cross_job_default_long_sustained_not_degraded",
        "ok": cross_default_long_not_degraded,
        "value": round_or_none(cross_default_wall, 3),
        "threshold": long_sustained_wall_ms,
    },
]
cross_default_performance_pass_count = sum(1 for item in cross_default_performance_checks if item["ok"])

latest_ratio = safe_float(latest_window.get("load_to_run_ratio"))
previous_ratio = safe_float(previous_window.get("load_to_run_ratio"))
top_ratio_improved = (
    safe_float((latest_window.get("top_load_to_run_ratio_window") or {}).get("load_to_run_ratio")) is not None
    and safe_float((previous_window.get("top_load_to_run_ratio_window") or {}).get("load_to_run_ratio")) is not None
    and safe_float((latest_window.get("top_load_to_run_ratio_window") or {}).get("load_to_run_ratio")) < safe_float((previous_window.get("top_load_to_run_ratio_window") or {}).get("load_to_run_ratio"))
)
top_load_improved = (
    safe_float((latest_window.get("top_load_window") or {}).get("load_ms")) is not None
    and safe_float((previous_window.get("top_load_window") or {}).get("load_ms")) is not None
    and safe_float((latest_window.get("top_load_window") or {}).get("load_ms")) < safe_float((previous_window.get("top_load_window") or {}).get("load_ms"))
)
overall_load_to_run_improved = latest_ratio is not None and previous_ratio is not None and latest_ratio < previous_ratio
reload_relief_observed = top_ratio_improved or top_load_improved or overall_load_to_run_improved

deployment_clean = (
    deployment.get("verdict") == "ok_dream7b_bpu_deployment_acceptance_probe"
    and deployment.get("check_count") == deployment.get("passed_check_count")
    and not deployment.get("errors")
)
promotion_clean = (
    promotion.get("verdict") == "ok_dream7b_bpu_selected_pair_service_promotion_gate_probe"
    and not promotion.get("errors")
    and isinstance(promotion.get("rollback_plan"), list)
)
promotion_allowed = promotion.get("promotion_allowed") is True
candidate_isolated = (promotion.get("live_services") or {}).get("candidate_service_isolated_from_default") is True
utilization_compliant = (
    utilization.get("diagnosis") == "hbm_reload_dominated"
    or (service_performance_floor_met and promotion_allowed)
)
legacy_service_default_deployable_ready = (
    service_clean
    and preferred_sustained_observed
    and deployment_clean
    and reload_relief_observed
    and service_performance_floor_met
    and promotion_clean
    and promotion_allowed
    and utilization_compliant
)
cross_job_service_base_ready = (
    cross_service_clean
    and cross_service_preferred_observed
    and deployment_clean
    and reload_relief_observed
    and cross_service_performance_pass_count >= min_performance_pass_count
    and cross_service_promotion_allowed
)
cross_job_service_ready_for_default_replacement = (
    cross_job_service_base_ready
    and cross_service_promotion.get("default_service_replaced") is False
)
cross_job_service_default_replaced = (
    cross_job_service_base_ready
    and cross_service_promotion.get("default_service_replaced") is True
    and cross_service_promotion.get("rollback_verified") is True
    and cross_default_clean
    and cross_default_preferred_observed
    and cross_default_performance_pass_count >= min_performance_pass_count
)
default_deployable_ready = legacy_service_default_deployable_ready or cross_job_service_default_replaced
default_deployable_status = (
    "ready"
    if default_deployable_ready
    else "ready_for_default_replacement_candidate_only"
    if cross_job_service_ready_for_default_replacement
    else "blocked_candidate_only"
)

blockers = []
if not default_deployable_ready:
    if not service_clean:
        blockers.append("service_sustained_telemetry_not_clean")
    if not preferred_sustained_observed:
        blockers.append("preferred_192_request_sustained_missing")
    if not deployment_clean:
        blockers.append("deployment_acceptance_not_clean")
    if not reload_relief_observed:
        blockers.append("reload_window_cost_not_improved")
    if not service_performance_floor_met:
        blockers.append("service_performance_pass_count_below_3")
    if not promotion_allowed:
        blockers.extend(promotion.get("promotion_blockers") or ["promotion_gate_blocked"])
    if service_avg_bpu is not None and service_avg_bpu < min_avg_bpu_loading:
        blockers.append("service_avg_bpu_below_default_deploy_threshold")
    if service_load_to_run is not None and service_load_to_run >= max_load_to_run_ratio:
        blockers.append("service_load_to_run_above_default_deploy_threshold")
if not default_deployable_ready and cross_job_prototype and cross_performance_pass_count >= 2:
    warnings.append("cross-job selected-pair reuse is a useful prototype but not a deployed service and still lacks three default-deploy performance passes")
if not default_deployable_ready and cross_queue_candidate and cross_queue_performance_pass_count < min_performance_pass_count:
    warnings.append("cross-job queue runner reduces load/run but still lacks three default-deploy performance passes")
if cross_job_service_ready_for_default_replacement:
    warnings.append("cross-job candidate service is ready for default replacement, but default_service_replaced is still false")
if not default_deployable_ready and cross_service_promotion.get("default_service_replaced") is True:
    if not cross_default_clean:
        blockers.append("cross_job_default_service_telemetry_not_clean")
    if not cross_default_preferred_observed:
        blockers.append("cross_job_default_service_preferred_192_missing")
    if cross_default_performance_pass_count < min_performance_pass_count:
        blockers.append("cross_job_default_service_performance_pass_count_below_3")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_default_deployable_acceptance_probe",
    "run_dir": str(run_dir),
    "report_root": str(report_root),
    "default_deployable_ready": default_deployable_ready,
    "default_deployable_status": default_deployable_status,
    "thresholds": {
        "min_processed_request_count": min_processed_request_count,
        "preferred_processed_request_count": preferred_processed_request_count,
        "target_wall_ms_per_request": target_wall_ms_per_request,
        "max_load_to_run_ratio": max_load_to_run_ratio,
        "target_load_to_run_ratio": target_load_to_run_ratio,
        "min_avg_bpu_loading": min_avg_bpu_loading,
        "target_avg_bpu_loading": target_avg_bpu_loading,
        "normal_use_wall_ms": normal_use_wall_ms,
        "long_sustained_wall_ms": long_sustained_wall_ms,
        "min_wall_delta_ratio": min_wall_delta_ratio,
        "min_performance_pass_count": min_performance_pass_count,
    },
    "evidence_paths": {
        "selected_pair_candidate_service_telemetry": str(service_path) if service_path else "",
        "selected_pair_cross_job_reuse": str(cross_job_path) if cross_job_path else "",
        "selected_pair_cross_job_queue_runner": str(cross_queue_path) if cross_queue_path else "",
        "selected_pair_cross_job_candidate_service_telemetry": str(cross_service_telemetry_path) if cross_service_telemetry_path else "",
        "selected_pair_cross_job_service_promotion_gate": str(cross_service_promotion_path) if cross_service_promotion_path else "",
        "cross_job_default_service_telemetry": str(cross_default_telemetry_path) if cross_default_telemetry_path else "",
        "deployment_acceptance": str(deployment_path) if deployment_path else "",
        "promotion_gate": str(promotion_path) if promotion_path else "",
        "reload_optimization": str(reload_path) if reload_path else "",
        "utilization_gap": str(utilization_path) if utilization_path else "",
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
    },
    "service_performance": {
        "performance_pass_count": service_performance_pass_count,
        "performance_floor_met": service_performance_floor_met,
        "amortized_wall_ms_per_processed_request": round_or_none(service_wall_ms, 3),
        "load_to_run_ratio": round_or_none(service_load_to_run),
        "avg_bpu_loading": round_or_none(service_avg_bpu, 3),
        "max_bpu_loading": service.get("max_bpu_loading"),
        "wall_delta_ratio_vs_normal_use": round_or_none(wall_delta_vs_normal_use),
        "checks": service_performance_checks,
    },
    "cross_job_prototype": {
        "prototype_clean": cross_job_prototype,
        "performance_pass_count": cross_performance_pass_count,
        "processed_forward_count": cross_job.get("processed_forward_count"),
        "amortized_wall_ms_per_forward": round_or_none(cross_wall, 3),
        "load_to_run_ratio": round_or_none(cross_load_to_run),
        "wall_delta_ratio_vs_normal_use": round_or_none(cross_wall_delta_vs_normal_use),
        "load_ms_delta_ratio_vs_service": cross_comparison.get("load_ms_delta_ratio"),
        "wall_ms_delta_ratio_vs_service": cross_comparison.get("wall_ms_delta_ratio"),
        "checks": cross_performance_checks,
    },
    "cross_job_queue_candidate": {
        "candidate_clean": cross_queue_candidate,
        "preferred_sustained_observed": cross_queue_preferred_observed,
        "performance_pass_count": cross_queue_performance_pass_count,
        "processed_request_count": cross_queue_processed,
        "failed_job_count": cross_queue_failed_jobs,
        "amortized_wall_ms_per_processed_request": round_or_none(cross_queue_wall, 3),
        "load_to_run_ratio": round_or_none(cross_queue_load_to_run),
        "wall_delta_ratio_vs_normal_use": round_or_none(cross_queue_wall_delta_vs_normal_use),
        "amortized_total_load_ms_per_processed_request": cross_queue.get("amortized_total_load_ms_per_processed_request"),
        "amortized_run_ms_per_processed_request": cross_queue.get("amortized_run_ms_per_processed_request"),
        "selected_pair": cross_queue.get("selected_pair"),
        "selected_segments": cross_queue.get("selected_segments"),
        "checks": cross_queue_performance_checks,
    },
    "cross_job_service_candidate": {
        "service_clean": cross_service_clean,
        "ready_for_default_replacement": cross_job_service_ready_for_default_replacement,
        "default_replaced_and_ready": cross_job_service_default_replaced,
        "default_service_replaced": cross_service_promotion.get("default_service_replaced"),
        "rollback_verified": cross_service_promotion.get("rollback_verified"),
        "preferred_sustained_observed": cross_service_preferred_observed,
        "performance_pass_count": cross_service_performance_pass_count,
        "processed_request_count": cross_service_processed,
        "failed_job_count": cross_service_failed_jobs,
        "amortized_wall_ms_per_processed_request": round_or_none(cross_service_wall, 3),
        "load_to_run_ratio": round_or_none(cross_service_load_to_run),
        "avg_bpu_loading": round_or_none(cross_service_avg_bpu, 3),
        "wall_delta_ratio_vs_normal_use": round_or_none(cross_service_wall_delta_vs_normal_use),
        "promotion_allowed": cross_service_promotion_allowed,
        "promotion_decision": cross_service_promotion.get("promotion_decision"),
        "promotion_blockers": cross_service_promotion.get("promotion_blockers"),
        "checks": cross_service_performance_checks,
    },
    "cross_job_default_service": {
        "service_clean": cross_default_clean,
        "preferred_sustained_observed": cross_default_preferred_observed,
        "performance_pass_count": cross_default_performance_pass_count,
        "processed_request_count": cross_default_processed,
        "failed_job_count": cross_default_failed_jobs,
        "amortized_wall_ms_per_processed_request": round_or_none(cross_default_wall, 3),
        "load_to_run_ratio": round_or_none(cross_default_load_to_run),
        "avg_bpu_loading": round_or_none(cross_default_avg_bpu, 3),
        "wall_delta_ratio_vs_normal_use": round_or_none(cross_default_wall_delta_vs_normal_use),
        "checks": cross_default_performance_checks,
    },
    "reload": {
        "reload_relief_observed": reload_relief_observed,
        "top_ratio_improved": top_ratio_improved,
        "top_load_improved": top_load_improved,
        "overall_load_to_run_improved": overall_load_to_run_improved,
        "latest_load_to_run_ratio": round_or_none(latest_ratio),
        "previous_load_to_run_ratio": round_or_none(previous_ratio),
    },
    "promotion": {
        "promotion_clean": promotion_clean,
        "promotion_allowed": promotion.get("promotion_allowed"),
        "promotion_decision": promotion.get("promotion_decision"),
        "promotion_blockers": promotion.get("promotion_blockers"),
        "candidate_isolated": candidate_isolated,
        "rollback_plan": promotion.get("rollback_plan"),
    },
    "utilization_statement": {
        "diagnosis": utilization.get("diagnosis"),
        "utilization_compliant": utilization_compliant,
        "max_bpu_loading_not_used_as_sole_success": True,
    },
    "blockers": sorted(set(blockers)),
    "evidence_gaps": evidence_gaps,
    "warnings": warnings,
}

(run_dir / "default_deployable_acceptance_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B BPU Default-Deployable Acceptance",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- default_deployable_ready: {payload['default_deployable_ready']}",
    f"- default_deployable_status: {payload['default_deployable_status']}",
    f"- processed_request_count: {processed_request_count}",
    f"- service_performance_pass_count: {service_performance_pass_count}/{min_performance_pass_count}",
    f"- cross_job_performance_pass_count: {cross_performance_pass_count}",
    f"- promotion_allowed: {promotion.get('promotion_allowed')}",
    f"- utilization_diagnosis: {utilization.get('diagnosis')}",
    "",
    "## Blockers",
    "",
]
if payload["blockers"]:
    lines.extend(f"- {item}" for item in payload["blockers"])
else:
    lines.append("- none")
lines.extend(["", "## Service Performance Checks", ""])
for item in service_performance_checks:
    lines.append(f"- {item['name']}: ok={item['ok']}, value={item['value']}, threshold={item['threshold']}")
lines.extend(["", "## Warnings", ""])
if warnings:
    lines.extend(f"- {item}" for item in warnings)
else:
    lines.append("- none")
(run_dir / "default_deployable_acceptance_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "default_deployable_acceptance_probe.md")
PY
