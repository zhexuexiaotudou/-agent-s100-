#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
best_load_to_run_ratio="${DREAM7B_BPU_RELOAD_OPTIMIZATION_BEST_LOAD_TO_RUN_RATIO:-9.468172}"
min_avg_bpu_loading_improvement="${DREAM7B_BPU_RELOAD_OPTIMIZATION_MIN_AVG_BPU_LOADING_IMPROVEMENT:-0.05}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$best_load_to_run_ratio" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_BPU_RELOAD_OPTIMIZATION_BEST_LOAD_TO_RUN_RATIO must be a non-negative number." >&2
  exit 2
fi
if ! [[ "$min_avg_bpu_loading_improvement" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_BPU_RELOAD_OPTIMIZATION_MIN_AVG_BPU_LOADING_IMPROVEMENT must be a non-negative number." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_reload_optimization_$stamp"
mkdir -p "$run_dir"

python3 - "$run_dir" "$report_root" "$best_load_to_run_ratio" "$min_avg_bpu_loading_improvement" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
best_load_to_run_ratio = float(sys.argv[3])
min_avg_bpu_loading_improvement = float(sys.argv[4])
errors = []
warnings = []


def latest_json(pattern):
    paths = [Path(item) for item in glob.glob(str(report_root / pattern))]
    paths = [item for item in paths if item.is_file()]
    if not paths:
        return None, {}
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def round_or_none(value, digits=6):
    value = safe_float(value)
    return round(value, digits) if value is not None else None


def bool_or_none(value):
    if isinstance(value, bool):
        return value
    return None


qwen_path, qwen = latest_json("s100_official_qwen_fullflow_*/official_qwen_fullflow_probe.json")
deepseek_path, deepseek = latest_json("s100_official_deepseek7b_baseline_*/deepseek7b_baseline_probe.json")
dream_oellm_path, dream_oellm = latest_json("dream7b_oellm_fullflow_feasibility_*/dream7b_oellm_fullflow_feasibility_probe.json")
cache_perf_path, cache_perf = latest_json("dream7b_bpu_hbm_cache_perf_*/summary.json")
persistent_pair_path, persistent_pair = latest_json("dream7b_bpu_persistent_pair_cache_*/persistent_pair_cache_probe.json")
persistent_segment_path, persistent_segment = latest_json("dream7b_bpu_persistent_segment_cache_*/persistent_segment_cache_probe.json")
persistent_triplet_path, persistent_triplet = latest_json("dream7b_bpu_persistent_triplet_topology_*/persistent_triplet_topology_probe.json")
window3_path, window3 = latest_json("dream7b_bpu_window3_forward_feasibility_*/window3_forward_feasibility_probe.json")
scheduling_path, scheduling = latest_json("dream7b_bpu_scheduling_params_*/scheduling_params_probe.json")
selected_pair_service_path, selected_pair_service = latest_json("dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json")
selected_pair_telemetry_path, selected_pair_telemetry = latest_json("dream7b_bpu_selected_pair_telemetry_*/selected_pair_telemetry_probe.json")
cross_job_path, cross_job = latest_json("dream7b_bpu_selected_pair_cross_job_reuse_*/selected_pair_cross_job_reuse_probe.json")
resplit_telemetry_path, resplit_telemetry = latest_json("dream7b_bpu_resplit_batch_telemetry_*/resplit_batch_telemetry_probe.json")
resplit_window_path, resplit_window = latest_json("dream7b_bpu_resplit_window_cost_*/resplit_window_cost_probe.json")
utilization_path, utilization = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
acceptance_path, acceptance = latest_json("dream7b_bpu_deployment_acceptance_*/deployment_acceptance_probe.json")

required = {
    "qwen_1_5b_512_128": qwen_path,
    "deepseek7b_fallback": deepseek_path,
    "dream7b_oellm": dream_oellm_path,
    "resplit_batch_telemetry": resplit_telemetry_path,
    "resplit_window_cost": resplit_window_path,
    "utilization_gap": utilization_path,
    "deployment_acceptance": acceptance_path,
}
for name, path in required.items():
    if not path:
        errors.append(f"missing required report for {name}")

forward_metrics = (resplit_telemetry or {}).get("forward_metrics") or {}
current_load_to_run_ratio = safe_float(forward_metrics.get("load_to_run_ratio"))
current_avg_bpu_loading = safe_float((resplit_telemetry or {}).get("avg_bpu_loading"))
current_wall_ms = safe_float(forward_metrics.get("wall_ms"))
selected_pair_metrics = (selected_pair_telemetry or {}).get("selected") or {}
selected_pair_wall_ms = safe_float(selected_pair_metrics.get("wall_ms"))
selected_pair_avg_bpu_loading = safe_float((selected_pair_telemetry or {}).get("avg_bpu_loading"))
selected_pair_wall_delta_ratio_vs_resplit = (
    (current_wall_ms - selected_pair_wall_ms) / current_wall_ms
    if current_wall_ms and selected_pair_wall_ms is not None
    else None
)
selected_pair_avg_bpu_delta_vs_resplit = (
    selected_pair_avg_bpu_loading - current_avg_bpu_loading
    if selected_pair_avg_bpu_loading is not None and current_avg_bpu_loading is not None
    else None
)
resplit_batch_count = safe_float((resplit_telemetry or {}).get("batch_count")) or safe_float(forward_metrics.get("batch_count"))
if not resplit_batch_count:
    results = (resplit_telemetry or {}).get("results") or []
    resplit_batch_count = len(results) if results else None
current_wall_ms_per_request = (
    current_wall_ms / resplit_batch_count
    if current_wall_ms is not None and resplit_batch_count
    else None
)
selected_pair_wall_ms_per_request = (
    selected_pair_wall_ms / resplit_batch_count
    if selected_pair_wall_ms is not None and resplit_batch_count
    else None
)
selected_pair_service_comparison = (selected_pair_service or {}).get("comparison_to_default_systemd_telemetry") or {}
selected_pair_service_wall_ms_per_request = safe_float((selected_pair_service or {}).get("amortized_wall_ms_per_processed_request"))
selected_pair_service_avg_bpu_loading = safe_float((selected_pair_service or {}).get("avg_bpu_loading"))
selected_pair_service_load_to_run_ratio = (
    safe_float((selected_pair_service or {}).get("total_load_ms")) / safe_float((selected_pair_service or {}).get("total_run_ms"))
    if safe_float((selected_pair_service or {}).get("total_run_ms"))
    else None
)
selected_pair_service_wall_delta_ratio_vs_resplit = (
    (current_wall_ms_per_request - selected_pair_service_wall_ms_per_request) / current_wall_ms_per_request
    if current_wall_ms_per_request and selected_pair_service_wall_ms_per_request is not None
    else None
)
selected_pair_service_avg_bpu_delta_vs_resplit = (
    selected_pair_service_avg_bpu_loading - current_avg_bpu_loading
    if selected_pair_service_avg_bpu_loading is not None and current_avg_bpu_loading is not None
    else None
)
selected_pair_service_wall_delta_ratio_vs_single = (
    (selected_pair_wall_ms_per_request - selected_pair_service_wall_ms_per_request) / selected_pair_wall_ms_per_request
    if selected_pair_wall_ms_per_request and selected_pair_service_wall_ms_per_request is not None
    else None
)
selected_pair_service_avg_bpu_delta_vs_single = (
    selected_pair_service_avg_bpu_loading - selected_pair_avg_bpu_loading
    if selected_pair_service_avg_bpu_loading is not None and selected_pair_avg_bpu_loading is not None
    else None
)
best_improved = current_load_to_run_ratio is not None and current_load_to_run_ratio < best_load_to_run_ratio
ratio_delta_vs_best = (
    current_load_to_run_ratio - best_load_to_run_ratio
    if current_load_to_run_ratio is not None
    else None
)

utilization_diagnosis = (utilization or {}).get("diagnosis")
acceptance_ok = (
    (acceptance or {}).get("verdict") == "ok_dream7b_bpu_deployment_acceptance_probe"
    and not (acceptance or {}).get("errors")
)

qwen_ok = (
    (qwen or {}).get("runtime_completed") is True
    and (qwen or {}).get("runtime_returncode") == 0
    and (qwen or {}).get("memory_alloc_failure_observed") is False
)
deepseek_blocked = (
    (deepseek or {}).get("decision") == "official_7b_runtime_blocked_common_buffer"
    and (deepseek or {}).get("bpu_alloc_request_bytes") == 7928846896
)
dream_registry_missing = (
    (dream_oellm or {}).get("failure_stage") == "registry_missing"
    and (dream_oellm or {}).get("dream_registered_in_official_sdk") is False
)

strategy_matrix = [
    {
        "strategy": "file_prefetch_or_local_hbm_cache",
        "probe": str(cache_perf_path) if cache_perf_path else "",
        "status": "bounded_prefetch_only" if cache_perf else "missing_evidence",
        "evidence": {
            "load_speedup_local_vs_nas": (cache_perf or {}).get("load_speedup_local_vs_nas"),
            "wall_speedup_local_vs_nas": (cache_perf or {}).get("wall_speedup_local_vs_nas"),
        },
        "decision": "Useful to remove NAS/file-cache variance, but it does not remove per-window HB_HBMRuntime load/release overhead.",
    },
    {
        "strategy": "persistent_pair_cache",
        "probe": str(persistent_pair_path) if persistent_pair_path else "",
        "status": "blocked_by_residency_boundary" if persistent_pair and persistent_pair.get("all_pair_workers_ready") is not True else "ready",
        "evidence": {
            "pair_worker_count": (persistent_pair or {}).get("pair_worker_count"),
            "ready_pair_worker_count": (persistent_pair or {}).get("ready_pair_worker_count"),
            "all_pair_workers_ready": (persistent_pair or {}).get("all_pair_workers_ready"),
            "launch_stopped_reason": (persistent_pair or {}).get("launch_stopped_reason"),
        },
        "decision": "Do not promote all-pair persistent workers until every pair can become ready under current memory limits.",
    },
    {
        "strategy": "persistent_segment_cache",
        "probe": str(persistent_segment_path) if persistent_segment_path else "",
        "status": "blocked_by_residency_boundary" if persistent_segment and persistent_segment.get("all_segment_workers_ready") is not True else "ready",
        "evidence": {
            "segment_worker_count": (persistent_segment or {}).get("segment_worker_count"),
            "ready_segment_worker_count": (persistent_segment or {}).get("ready_segment_worker_count"),
            "max_resident_segment_count_observed": (persistent_segment or {}).get("max_resident_segment_count_observed"),
            "launch_stopped_reason": (persistent_segment or {}).get("launch_stopped_reason"),
        },
        "decision": "Current whole-segment persistence is bounded; use selective residency only.",
    },
    {
        "strategy": "persistent_triplet_topology",
        "probe": str(persistent_triplet_path) if persistent_triplet_path else "",
        "status": "topology_stable_but_forward_blocked" if persistent_triplet and window3 and window3.get("direct_window3_forward_supported") is False else "needs_check",
        "evidence": {
            "stable_triplet_topology_count": (persistent_triplet or {}).get("stable_triplet_topology_count"),
            "selected_topology": (persistent_triplet or {}).get("selected_topology"),
            "direct_window3_forward_supported": (window3 or {}).get("direct_window3_forward_supported"),
            "expected_window3_failure_observed": (window3 or {}).get("expected_window3_failure_observed"),
        },
        "decision": "Triplet residency maps are useful for planning, but direct window3 forward is not the current execution path.",
    },
    {
        "strategy": "selected_pair_cross_job_cache",
        "probe": str(selected_pair_telemetry_path) if selected_pair_telemetry_path else str(cross_job_path) if cross_job_path else str(selected_pair_service_path) if selected_pair_service_path else "",
        "status": (
            "batch16_wall_candidate"
            if selected_pair_wall_delta_ratio_vs_resplit is not None and selected_pair_wall_delta_ratio_vs_resplit > 0
            else "partial_load_improvement" if cross_job or selected_pair_service else "missing_evidence"
        ),
        "evidence": {
            "selected_pair_telemetry_path": str(selected_pair_telemetry_path) if selected_pair_telemetry_path else "",
            "selected_pair": selected_pair_metrics.get("selected_pair"),
            "selected_pair_covers_all_segments": selected_pair_metrics.get("selected_pair_covers_all_segments"),
            "selected_pair_wall_ms": round_or_none(selected_pair_wall_ms, 3),
            "resplit_wall_ms": round_or_none(current_wall_ms, 3),
            "selected_pair_wall_delta_ratio_vs_resplit": round_or_none(selected_pair_wall_delta_ratio_vs_resplit, 6),
            "selected_pair_avg_bpu_loading": round_or_none(selected_pair_avg_bpu_loading, 3),
            "selected_pair_avg_bpu_delta_vs_resplit": round_or_none(selected_pair_avg_bpu_delta_vs_resplit, 3),
            "candidate_wall_time_improved_vs_default_systemd": ((selected_pair_service or {}).get("comparison_to_default_systemd_telemetry") or {}).get("candidate_wall_time_improved_vs_default_systemd"),
            "candidate_avg_bpu_loading_not_worse_than_default_systemd": ((selected_pair_service or {}).get("comparison_to_default_systemd_telemetry") or {}).get("candidate_avg_bpu_loading_not_worse_than_default_systemd"),
            "cross_job_load_time_improved": ((cross_job or {}).get("comparison_to_selected_pair_candidate_service") or {}).get("cross_job_load_time_improved"),
            "cross_job_wall_time_improved": ((cross_job or {}).get("comparison_to_selected_pair_candidate_service") or {}).get("cross_job_wall_time_improved"),
        },
        "decision": "Keep as a utilization-progress candidate only when selected-pair batch16 wall time or average BPU loading improves against the latest resplit-topwindow telemetry; validate with sustained service telemetry before default promotion.",
    },
    {
        "strategy": "window_scheduling_resplit_topwindow",
        "probe": str(resplit_window_path) if resplit_window_path else "",
        "status": "best_improved" if best_improved else "not_better_than_current_best",
        "evidence": {
            "segment_plan": forward_metrics.get("segment_plan"),
            "window_execution_mode": forward_metrics.get("window_execution_mode"),
            "load_to_run_ratio": round_or_none(current_load_to_run_ratio),
            "best_load_to_run_ratio": best_load_to_run_ratio,
            "ratio_delta_vs_best": round_or_none(ratio_delta_vs_best),
            "avg_bpu_loading": round_or_none(current_avg_bpu_loading, 3),
            "top_load_window": (resplit_window or {}).get("top_load_window"),
            "top_load_to_run_ratio_window": (resplit_window or {}).get("top_load_to_run_ratio_window"),
        },
        "decision": "Only call this utilization progress if load/run, average BPU loading, or batch wall time improves versus the best accepted baseline.",
    },
    {
        "strategy": "bpu_core_scheduling",
        "probe": str(scheduling_path) if scheduling_path else "",
        "status": "core0_only" if scheduling and scheduling.get("core0_explicit_supported") is True and scheduling.get("nonzero_cores_supported") is False else "needs_check",
        "evidence": {
            "core0_explicit_supported": (scheduling or {}).get("core0_explicit_supported"),
            "nonzero_cores_supported": (scheduling or {}).get("nonzero_cores_supported"),
            "run_ok_by_core": (scheduling or {}).get("run_ok_by_core"),
        },
        "decision": "Do not copy Qwen bpu_core sweep values into Dream; keep scheduling changes constrained to verified Dream runtime support.",
    },
]

if not qwen_ok:
    warnings.append("latest Qwen 1.5B official baseline is not proven runnable by the selected report")
if not deepseek_blocked:
    warnings.append("latest DeepSeek 7B fallback report does not show the expected common-buffer block")
if not dream_registry_missing:
    warnings.append("latest Dream OELLM report does not show the expected registry_missing block")
if utilization_diagnosis != "hbm_reload_dominated":
    warnings.append(f"latest utilization diagnosis is not hbm_reload_dominated: {utilization_diagnosis}")
if not acceptance_ok:
    errors.append("latest Dream deployment acceptance is not clean")

selected_pair_wall_improved = selected_pair_wall_delta_ratio_vs_resplit is not None and selected_pair_wall_delta_ratio_vs_resplit > 0
selected_pair_avg_bpu_improved = (
    selected_pair_avg_bpu_delta_vs_resplit is not None
    and selected_pair_avg_bpu_delta_vs_resplit >= min_avg_bpu_loading_improvement
)
sustained_service_wall_improved = (
    selected_pair_service_wall_delta_ratio_vs_resplit is not None
    and selected_pair_service_wall_delta_ratio_vs_resplit > 0
)
sustained_service_avg_bpu_improved = (
    selected_pair_service_avg_bpu_delta_vs_resplit is not None
    and selected_pair_service_avg_bpu_delta_vs_resplit >= min_avg_bpu_loading_improvement
)
sustained_service_clean = (
    (selected_pair_service or {}).get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe"
    and not (selected_pair_service or {}).get("errors")
    and int((selected_pair_service or {}).get("processed_request_count") or 0) >= 48
)
sustained_service_decision = (
    "guarded_sustained_wall_time_candidate"
    if sustained_service_clean and sustained_service_wall_improved
    else "not_promoted"
)
default_service_replacement_decision = "do_not_replace_default_service_yet"
substantial_improvement = bool(
    best_improved
    or selected_pair_wall_improved
    or selected_pair_avg_bpu_improved
    or (sustained_service_clean and sustained_service_wall_improved)
    or (sustained_service_clean and sustained_service_avg_bpu_improved)
)
if not substantial_improvement:
    final_decision = "keep_hbm_reload_dominated"
    next_action = "Do not claim 128TOPS utilization progress; ask vendor about official 7B memory layout and Dream adapter while testing lower-reload orchestration candidates."
elif sustained_service_decision == "guarded_sustained_wall_time_candidate":
    final_decision = "guarded_sustained_wall_time_candidate"
    next_action = "Keep selected-pair candidate service as a rollback-gated wall-time candidate; do not replace the default service until average BPU loading or load/run also improves under sustained telemetry."
else:
    final_decision = "utilization_progress_candidate"
    next_action = "Treat selected-pair resident execution as a guarded utilization-progress candidate; run sustained service telemetry and acceptance before any default-service promotion."

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_reload_optimization_probe" if not errors else "failed_dream7b_bpu_reload_optimization_probe",
    "run_dir": str(run_dir),
    "best_load_to_run_ratio": best_load_to_run_ratio,
    "min_avg_bpu_loading_improvement": min_avg_bpu_loading_improvement,
    "evidence_paths": {name: str(path) if path else "" for name, path in required.items()},
    "support_closure": {
        "qwen_1_5b_512_128_verified_runnable": qwen_ok,
        "deepseek7b_common_buffer_blocked": deepseek_blocked,
        "dream7b_oellm_registry_missing": dream_registry_missing,
        "vendor_questions_required": [
            "What S100P memory layout or runtime settings are required to load DeepSeek_R1_Distill_Qwen_7B_1024.hbm?",
            "Is there an official Dream/DreamModel adapter or supported plugin path for oellm_build/leap_llm?",
        ],
    },
    "current_resplit_metrics": {
        "telemetry_path": str(resplit_telemetry_path) if resplit_telemetry_path else "",
        "window_cost_path": str(resplit_window_path) if resplit_window_path else "",
        "utilization_gap_path": str(utilization_path) if utilization_path else "",
        "acceptance_path": str(acceptance_path) if acceptance_path else "",
        "load_to_run_ratio": round_or_none(current_load_to_run_ratio),
        "ratio_delta_vs_best": round_or_none(ratio_delta_vs_best),
        "avg_bpu_loading": round_or_none(current_avg_bpu_loading, 3),
        "wall_ms": round_or_none(current_wall_ms, 3),
        "diagnosis": utilization_diagnosis,
        "acceptance_ok": acceptance_ok,
    },
    "selected_pair_candidate_metrics": {
        "selected_pair_telemetry_path": str(selected_pair_telemetry_path) if selected_pair_telemetry_path else "",
        "selected_pair": selected_pair_metrics.get("selected_pair"),
        "selected_pair_covers_all_segments": selected_pair_metrics.get("selected_pair_covers_all_segments"),
        "wall_ms": round_or_none(selected_pair_wall_ms, 3),
        "wall_ms_per_request": round_or_none(selected_pair_wall_ms_per_request, 3),
        "avg_bpu_loading": round_or_none(selected_pair_avg_bpu_loading, 3),
        "wall_delta_ratio_vs_resplit": round_or_none(selected_pair_wall_delta_ratio_vs_resplit, 6),
        "avg_bpu_delta_vs_resplit": round_or_none(selected_pair_avg_bpu_delta_vs_resplit, 3),
        "selected_pair_wall_improved_vs_resplit": selected_pair_wall_improved,
        "selected_pair_avg_bpu_improved_vs_resplit": selected_pair_avg_bpu_improved,
    },
    "sustained_service_candidate_metrics": {
        "selected_pair_service_telemetry_path": str(selected_pair_service_path) if selected_pair_service_path else "",
        "service_verdict": (selected_pair_service or {}).get("verdict"),
        "service_clean": sustained_service_clean,
        "processed_request_count": (selected_pair_service or {}).get("processed_request_count"),
        "batch_counts": (selected_pair_service or {}).get("batch_counts"),
        "amortized_wall_ms_per_processed_request": round_or_none(selected_pair_service_wall_ms_per_request, 3),
        "amortized_load_ms_per_processed_request": round_or_none((selected_pair_service or {}).get("amortized_load_ms_per_processed_request"), 3),
        "amortized_run_ms_per_processed_request": round_or_none((selected_pair_service or {}).get("amortized_run_ms_per_processed_request"), 3),
        "load_to_run_ratio": round_or_none(selected_pair_service_load_to_run_ratio, 6),
        "avg_bpu_loading": round_or_none(selected_pair_service_avg_bpu_loading, 3),
        "max_bpu_loading": round_or_none((selected_pair_service or {}).get("max_bpu_loading"), 3),
        "wall_delta_ratio_vs_resplit_per_request": round_or_none(selected_pair_service_wall_delta_ratio_vs_resplit, 6),
        "avg_bpu_delta_vs_resplit": round_or_none(selected_pair_service_avg_bpu_delta_vs_resplit, 3),
        "wall_delta_ratio_vs_selected_pair_single_request": round_or_none(selected_pair_service_wall_delta_ratio_vs_single, 6),
        "avg_bpu_delta_vs_selected_pair_single": round_or_none(selected_pair_service_avg_bpu_delta_vs_single, 3),
        "comparison_to_default_systemd_telemetry": selected_pair_service_comparison,
        "sustained_service_wall_improved_vs_resplit": sustained_service_wall_improved,
        "sustained_service_avg_bpu_improved_vs_resplit": sustained_service_avg_bpu_improved,
        "sustained_service_decision": sustained_service_decision,
        "default_service_replacement_decision": default_service_replacement_decision,
    },
    "strategy_matrix": strategy_matrix,
    "substantial_improvement_observed": substantial_improvement,
    "final_decision": final_decision,
    "next_action": next_action,
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "reload_optimization_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Reload Optimization Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- best_load_to_run_ratio: {best_load_to_run_ratio}",
    f"- current_load_to_run_ratio: {payload['current_resplit_metrics']['load_to_run_ratio']}",
    f"- ratio_delta_vs_best: {payload['current_resplit_metrics']['ratio_delta_vs_best']}",
    f"- avg_bpu_loading: {payload['current_resplit_metrics']['avg_bpu_loading']}",
    f"- diagnosis: {payload['current_resplit_metrics']['diagnosis']}",
    f"- selected_pair_wall_ms: {payload['selected_pair_candidate_metrics']['wall_ms']}",
    f"- selected_pair_avg_bpu_loading: {payload['selected_pair_candidate_metrics']['avg_bpu_loading']}",
    f"- selected_pair_wall_delta_ratio_vs_resplit: {payload['selected_pair_candidate_metrics']['wall_delta_ratio_vs_resplit']}",
    f"- sustained_service_amortized_wall_ms_per_request: {payload['sustained_service_candidate_metrics']['amortized_wall_ms_per_processed_request']}",
    f"- sustained_service_avg_bpu_loading: {payload['sustained_service_candidate_metrics']['avg_bpu_loading']}",
    f"- sustained_service_wall_delta_ratio_vs_resplit_per_request: {payload['sustained_service_candidate_metrics']['wall_delta_ratio_vs_resplit_per_request']}",
    f"- sustained_service_decision: {payload['sustained_service_candidate_metrics']['sustained_service_decision']}",
    f"- default_service_replacement_decision: {payload['sustained_service_candidate_metrics']['default_service_replacement_decision']}",
    f"- final_decision: {final_decision}",
    f"- next_action: {next_action}",
    "",
    "## External Support Closure",
    "",
    f"- qwen_1_5b_512_128_verified_runnable: {qwen_ok}",
    f"- deepseek7b_common_buffer_blocked: {deepseek_blocked}",
    f"- dream7b_oellm_registry_missing: {dream_registry_missing}",
    "",
    "## Strategy Matrix",
    "",
    "| Strategy | Status | Decision |",
    "| --- | --- | --- |",
]
for item in strategy_matrix:
    lines.append(f"| {item['strategy']} | {item['status']} | {item['decision']} |")
lines.extend(["", "## Errors", ""])
if errors:
    lines.extend(f"- {item}" for item in errors)
else:
    lines.append("- none")
lines.extend(["", "## Warnings", ""])
if warnings:
    lines.extend(f"- {item}" for item in warnings)
else:
    lines.append("- none")
(run_dir / "reload_optimization_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "reload_optimization_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
