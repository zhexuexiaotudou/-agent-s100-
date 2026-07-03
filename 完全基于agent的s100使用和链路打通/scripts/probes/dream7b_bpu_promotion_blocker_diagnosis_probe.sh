#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
best_load_to_run_ratio="${DREAM7B_BPU_PROMOTION_BLOCKER_BEST_LOAD_TO_RUN_RATIO:-9.468172}"
min_wall_delta_ratio="${DREAM7B_BPU_PROMOTION_BLOCKER_MIN_WALL_DELTA_RATIO:-0.05}"
min_avg_bpu_delta="${DREAM7B_BPU_PROMOTION_BLOCKER_MIN_AVG_BPU_DELTA:-0.0}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

for item in "$best_load_to_run_ratio" "$min_wall_delta_ratio" "$min_avg_bpu_delta"; do
  if ! [[ "$item" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
    echo "Promotion blocker numeric thresholds must be valid numbers." >&2
    exit 2
  fi
done

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_promotion_blocker_diagnosis_$stamp"
mkdir -p "$run_dir"

python3 - "$run_dir" "$report_root" "$best_load_to_run_ratio" "$min_wall_delta_ratio" "$min_avg_bpu_delta" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
best_load_to_run_ratio = float(sys.argv[3])
min_wall_delta_ratio = float(sys.argv[4])
min_avg_bpu_delta = float(sys.argv[5])
errors = []
warnings = []


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


def round_or_none(value, digits=6):
    value = safe_float(value)
    return round(value, digits) if value is not None else None


promotion_path, promotion = latest_json("dream7b_bpu_selected_pair_service_promotion_gate_*/selected_pair_service_promotion_gate_probe.json")
service_path, service = latest_json("dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json")
selected_path, selected = latest_json("dream7b_bpu_selected_pair_telemetry_*/selected_pair_telemetry_probe.json")
resplit_path, resplit = latest_json("dream7b_bpu_resplit_batch_telemetry_*/resplit_batch_telemetry_probe.json")
window_path, window = latest_json("dream7b_bpu_resplit_window_cost_*/resplit_window_cost_probe.json")
capacity_path, capacity = latest_json("dream7b_bpu_segment_capacity_planner_*/segment_capacity_planner_probe.json")
utilization_path, utilization = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
reload_path, reload = latest_json("dream7b_bpu_reload_optimization_*/reload_optimization_probe.json")
acceptance_path, acceptance = latest_json("dream7b_bpu_deployment_acceptance_*/deployment_acceptance_probe.json")

required = {
    "promotion_gate": promotion_path,
    "sustained_service_telemetry": service_path,
    "selected_pair_single_telemetry": selected_path,
    "resplit_topwindow_telemetry": resplit_path,
    "resplit_window_cost": window_path,
    "segment_capacity_planner": capacity_path,
    "utilization_gap": utilization_path,
    "reload_optimization": reload_path,
    "deployment_acceptance": acceptance_path,
}
for name, path in required.items():
    if not path:
        errors.append(f"missing required report: {name}")

for name, payload, expected in (
    ("promotion_gate", promotion, "ok_dream7b_bpu_selected_pair_service_promotion_gate_probe"),
    ("sustained_service_telemetry", service, "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe"),
    ("selected_pair_single_telemetry", selected, "ok_dream7b_bpu_selected_pair_telemetry_probe"),
    ("resplit_topwindow_telemetry", resplit, "ok_dream7b_bpu_resplit_batch_telemetry_probe"),
    ("resplit_window_cost", window, "ok_dream7b_bpu_resplit_window_cost_probe"),
    ("segment_capacity_planner", capacity, "ok_dream7b_bpu_segment_capacity_planner_probe"),
    ("utilization_gap", utilization, "ok_dream7b_bpu_utilization_gap_probe"),
    ("reload_optimization", reload, "ok_dream7b_bpu_reload_optimization_probe"),
    ("deployment_acceptance", acceptance, "ok_dream7b_bpu_deployment_acceptance_probe"),
):
    if payload and payload.get("verdict") != expected:
        errors.append(f"{name} unexpected verdict: {payload.get('verdict')}")
    if payload and payload.get("errors"):
        errors.append(f"{name} contains errors: {payload.get('errors')}")

promotion_metrics = promotion.get("metrics") or {}
service_comparison = service.get("comparison_to_default_systemd_telemetry") or {}
selected_metrics = selected.get("selected") or {}
resplit_metrics = resplit.get("forward_metrics") or {}
reload_sustained = reload.get("sustained_service_candidate_metrics") or {}
capacity_status = capacity.get("current_split_capacity") or {}

service_wall = safe_float(service.get("amortized_wall_ms_per_processed_request"))
service_load_to_run = safe_float(promotion_metrics.get("candidate_load_to_run_ratio"), safe_float(reload_sustained.get("load_to_run_ratio"), safe_float(service.get("load_to_run_ratio"))))
service_avg_bpu = safe_float(service.get("avg_bpu_loading"))
single_wall = safe_float(selected_metrics.get("wall_ms"))
single_batch_count = safe_float(selected.get("batch_count"))
single_wall_per_request = single_wall / single_batch_count if single_wall is not None and single_batch_count else None
single_avg_bpu = safe_float(selected.get("avg_bpu_loading"))
resplit_wall = safe_float(resplit_metrics.get("wall_ms"))
resplit_batch_count = safe_float(resplit.get("batch_count"))
resplit_wall_per_request = resplit_wall / resplit_batch_count if resplit_wall is not None and resplit_batch_count else None
resplit_avg_bpu = safe_float(resplit.get("avg_bpu_loading"))
resplit_load_to_run = safe_float(resplit_metrics.get("load_to_run_ratio"))

load_to_run_delta_vs_best = service_load_to_run - best_load_to_run_ratio if service_load_to_run is not None else None
load_to_run_delta_vs_resplit = service_load_to_run - resplit_load_to_run if service_load_to_run is not None and resplit_load_to_run is not None else None
avg_bpu_delta_vs_resplit = service_avg_bpu - resplit_avg_bpu if service_avg_bpu is not None and resplit_avg_bpu is not None else None
avg_bpu_delta_vs_single = service_avg_bpu - single_avg_bpu if service_avg_bpu is not None and single_avg_bpu is not None else None
wall_delta_vs_resplit = (resplit_wall_per_request - service_wall) / resplit_wall_per_request if resplit_wall_per_request and service_wall is not None else None
wall_delta_vs_single = (single_wall_per_request - service_wall) / single_wall_per_request if single_wall_per_request and service_wall is not None else None
wall_delta_vs_default = safe_float(service_comparison.get("wall_ms_delta_ratio_vs_default_systemd"))
avg_bpu_delta_vs_default = safe_float(service_comparison.get("avg_bpu_loading_delta_vs_default_systemd"))

top_load_window = window.get("top_load_window") or {}
top_ratio_window = window.get("top_load_to_run_ratio_window") or {}
top_total_window = window.get("top_total_window") or {}
promotion_blockers = promotion.get("promotion_blockers") or []

blocker_sources = [
    {
        "blocker": "promotion_average_bpu_not_worse_vs_default",
        "observed": round_or_none(avg_bpu_delta_vs_default, 3),
        "required": ">= 0.0 or candidate_avg_bpu_loading_not_worse_than_default_systemd: True",
        "source": str(service_path) if service_path else "",
        "status": "blocked" if "promotion_average_bpu_not_worse_vs_default" in promotion_blockers else "passed",
    },
    {
        "blocker": "promotion_average_bpu_improved_vs_resplit",
        "observed": round_or_none(avg_bpu_delta_vs_resplit, 3),
        "required": f">= {min_avg_bpu_delta}",
        "source": str(reload_path) if reload_path else "",
        "status": "blocked" if "promotion_average_bpu_improved_vs_resplit" in promotion_blockers else "passed",
    },
    {
        "blocker": "promotion_load_to_run_not_worse_than_best",
        "observed": round_or_none(service_load_to_run, 6),
        "required": f"<= {best_load_to_run_ratio}",
        "delta_vs_required": round_or_none(load_to_run_delta_vs_best, 6),
        "source": str(promotion_path) if promotion_path else "",
        "status": "blocked" if "promotion_load_to_run_not_worse_than_best" in promotion_blockers else "passed",
    },
    {
        "blocker": "promotion_not_hbm_reload_dominated",
        "observed": utilization.get("diagnosis"),
        "required": "not hbm_reload_dominated",
        "source": str(utilization_path) if utilization_path else "",
        "status": "blocked" if "promotion_not_hbm_reload_dominated" in promotion_blockers else "passed",
    },
    {
        "blocker": "reload_gate_allows_default_replacement",
        "observed": reload_sustained.get("default_service_replacement_decision"),
        "required": "not do_not_replace_default_service_yet",
        "source": str(reload_path) if reload_path else "",
        "status": "blocked" if "reload_gate_allows_default_replacement" in promotion_blockers else "passed",
    },
]

next_candidates = [
    {
        "priority": 1,
        "candidate": "prefix_micro_window_reload_reduction",
        "target_windows": [top_ratio_window.get("resident_segments")],
        "rationale": "The highest load/run window is dominated by HBM load rather than BPU run time; reducing this fixed reload cost is the most direct path to improve load/run.",
        "evidence": {
            "resident_segments": top_ratio_window.get("resident_segments"),
            "load_ms": top_ratio_window.get("load_ms"),
            "run_ms": top_ratio_window.get("run_ms"),
            "load_to_run_ratio": top_ratio_window.get("load_to_run_ratio"),
            "load_share": top_ratio_window.get("load_share"),
        },
        "acceptance_threshold": {
            "candidate_load_to_run_ratio": f"<= {best_load_to_run_ratio}",
            "avg_bpu_delta_vs_resplit": f">= {min_avg_bpu_delta}",
        },
    },
    {
        "priority": 2,
        "candidate": "seg02_04_seg04_07_window_cost_reduction",
        "target_windows": [top_load_window.get("resident_segments"), top_total_window.get("resident_segments")],
        "rationale": "The largest absolute load and total-window cost still sits around seg02_04/seg04_07; selected-pair anchors seg02_04 but does not remove the remaining seg04_07 load boundary.",
        "evidence": {
            "resident_segments": top_load_window.get("resident_segments"),
            "load_ms": top_load_window.get("load_ms"),
            "run_ms": top_load_window.get("run_ms"),
            "total_window_ms": top_load_window.get("total_window_ms"),
            "load_share": top_load_window.get("load_share"),
        },
        "acceptance_threshold": {
            "wall_delta_ratio_vs_resplit_per_request": f">= {min_wall_delta_ratio}",
            "candidate_avg_bpu_loading_not_worse_than_default_systemd": True,
        },
    },
    {
        "priority": 3,
        "candidate": "resident_capacity_boundary_experiment",
        "target_windows": [capacity_status.get("selected_topology")],
        "rationale": "Capacity planner shows no successful seeded quad and max resident segment count remains bounded, so any larger resident set must first prove residency before service promotion.",
        "evidence": {
            "max_resident_segment_count_observed": capacity_status.get("max_resident_segment_count_observed"),
            "successful_seeded_quad_count": capacity_status.get("successful_seeded_quad_count"),
            "recommended_anchor_segment_indexes": capacity.get("recommended_anchor_segment_indexes"),
            "recommended_resplit_segment_indexes": capacity.get("recommended_resplit_segment_indexes"),
        },
        "acceptance_threshold": {
            "successful_seeded_quad_count": "> 0 before any four-resident forward path",
            "default_service_replaced": False,
        },
    },
    {
        "priority": 4,
        "candidate": "core0_only_scheduling_control",
        "target_windows": ["all current selected-pair runs"],
        "rationale": "Scheduling evidence allows core0-only checks but nonzero cores are unsupported; use this only as a controlled variable, not as a primary 128TOPS claim.",
        "evidence": {
            "reload_final_decision": reload.get("final_decision"),
            "bpu_core_scheduling_status": "core0_only",
        },
        "acceptance_threshold": {
            "avg_bpu_loading": "must improve under same 48-request sustained workload",
            "wall_time": "must not regress by more than 5%",
        },
    },
]

if promotion.get("promotion_decision") != "block_default_service_replacement":
    warnings.append(f"latest promotion gate decision is not blocking replacement: {promotion.get('promotion_decision')}")
if service_load_to_run is not None and service_load_to_run <= best_load_to_run_ratio:
    warnings.append("candidate service load/run already beats best threshold; check whether promotion blocker report is stale")
if avg_bpu_delta_vs_resplit is not None and avg_bpu_delta_vs_resplit >= min_avg_bpu_delta:
    warnings.append("candidate service average BPU already meets resplit threshold; check whether promotion blocker report is stale")

diagnosis = {
    "summary": "wall_time_improved_but_utilization_not_promotable",
    "promotion_blocked": bool(promotion_blockers),
    "dominant_blocker_family": "hbm_reload_and_average_bpu",
    "default_service_replacement_allowed": False,
    "recommended_next_goal": "run a targeted prefix/top-load window reload-reduction experiment, then rerun sustained service telemetry and promotion gate",
}

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_promotion_blocker_diagnosis_probe" if not errors else "failed_dream7b_bpu_promotion_blocker_diagnosis_probe",
    "run_dir": str(run_dir),
    "report_root": str(report_root),
    "best_load_to_run_ratio": best_load_to_run_ratio,
    "min_wall_delta_ratio": min_wall_delta_ratio,
    "min_avg_bpu_delta": min_avg_bpu_delta,
    "evidence_paths": {name: str(path) if path else "" for name, path in required.items()},
    "diagnosis": diagnosis,
    "promotion_blockers": promotion_blockers,
    "blocker_sources": blocker_sources,
    "metric_deltas": {
        "service_amortized_wall_ms_per_request": round_or_none(service_wall, 3),
        "single_pair_wall_ms_per_request": round_or_none(single_wall_per_request, 3),
        "resplit_wall_ms_per_request": round_or_none(resplit_wall_per_request, 3),
        "wall_delta_ratio_vs_default_systemd": round_or_none(wall_delta_vs_default, 6),
        "wall_delta_ratio_vs_resplit_per_request": round_or_none(wall_delta_vs_resplit, 6),
        "wall_delta_ratio_vs_selected_pair_single_request": round_or_none(wall_delta_vs_single, 6),
        "service_avg_bpu_loading": round_or_none(service_avg_bpu, 3),
        "selected_pair_single_avg_bpu_loading": round_or_none(single_avg_bpu, 3),
        "resplit_avg_bpu_loading": round_or_none(resplit_avg_bpu, 3),
        "avg_bpu_delta_vs_default_systemd": round_or_none(avg_bpu_delta_vs_default, 3),
        "avg_bpu_delta_vs_resplit": round_or_none(avg_bpu_delta_vs_resplit, 3),
        "avg_bpu_delta_vs_selected_pair_single": round_or_none(avg_bpu_delta_vs_single, 3),
        "candidate_load_to_run_ratio": round_or_none(service_load_to_run, 6),
        "resplit_load_to_run_ratio": round_or_none(resplit_load_to_run, 6),
        "load_to_run_delta_vs_best": round_or_none(load_to_run_delta_vs_best, 6),
        "load_to_run_delta_vs_resplit": round_or_none(load_to_run_delta_vs_resplit, 6),
    },
    "window_bottlenecks": {
        "top_load_window": top_load_window,
        "top_load_to_run_ratio_window": top_ratio_window,
        "top_total_window": top_total_window,
    },
    "capacity_boundary": {
        "max_resident_segment_count_observed": capacity_status.get("max_resident_segment_count_observed"),
        "successful_seeded_quad_count": capacity_status.get("successful_seeded_quad_count"),
        "current_split_quad_residency_supported": capacity_status.get("current_split_quad_residency_supported"),
        "recommended_anchor_segment_indexes": capacity.get("recommended_anchor_segment_indexes"),
        "recommended_resplit_segment_indexes": capacity.get("recommended_resplit_segment_indexes"),
    },
    "next_optimization_candidates": next_candidates,
    "promotion_decision": "keep_candidate_only_until_blockers_clear",
    "next_action": diagnosis["recommended_next_goal"],
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "promotion_blocker_diagnosis_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Promotion Blocker Diagnosis",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- promotion_decision: {payload['promotion_decision']}",
    f"- diagnosis_summary: {diagnosis['summary']}",
    f"- dominant_blocker_family: {diagnosis['dominant_blocker_family']}",
    f"- default_service_replacement_allowed: {diagnosis['default_service_replacement_allowed']}",
    f"- candidate_load_to_run_ratio: {payload['metric_deltas']['candidate_load_to_run_ratio']}",
    f"- load_to_run_delta_vs_best: {payload['metric_deltas']['load_to_run_delta_vs_best']}",
    f"- service_avg_bpu_loading: {payload['metric_deltas']['service_avg_bpu_loading']}",
    f"- avg_bpu_delta_vs_resplit: {payload['metric_deltas']['avg_bpu_delta_vs_resplit']}",
    f"- wall_delta_ratio_vs_resplit_per_request: {payload['metric_deltas']['wall_delta_ratio_vs_resplit_per_request']}",
    f"- next_action: {payload['next_action']}",
    "",
    "## Promotion Blockers",
    "",
]
lines.extend(f"- {item}" for item in promotion_blockers) if promotion_blockers else lines.append("- none")
lines.extend(["", "## Top Window Bottlenecks", ""])
for name, item in payload["window_bottlenecks"].items():
    lines.append(f"- {name}: resident_segments={item.get('resident_segments')} load_ms={item.get('load_ms')} run_ms={item.get('run_ms')} load_to_run_ratio={item.get('load_to_run_ratio')}")
lines.extend(["", "## Next Optimization Candidates", ""])
for item in next_candidates:
    lines.append(f"- P{item['priority']} {item['candidate']}: {item['rationale']}")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "promotion_blocker_diagnosis_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "promotion_blocker_diagnosis_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
