#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
best_load_to_run_ratio="${DREAM7B_FINAL_ACCEPTANCE_BEST_LOAD_TO_RUN_RATIO:-9.468172}"
min_wall_delta_ratio="${DREAM7B_FINAL_ACCEPTANCE_MIN_WALL_DELTA_RATIO:-0.05}"
min_sustained_request_count="${DREAM7B_FINAL_ACCEPTANCE_MIN_SUSTAINED_REQUEST_COUNT:-48}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! [[ "$best_load_to_run_ratio" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_FINAL_ACCEPTANCE_BEST_LOAD_TO_RUN_RATIO must be a non-negative number." >&2
  exit 2
fi
if ! [[ "$min_wall_delta_ratio" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "DREAM7B_FINAL_ACCEPTANCE_MIN_WALL_DELTA_RATIO must be a non-negative number." >&2
  exit 2
fi
if ! [[ "$min_sustained_request_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "DREAM7B_FINAL_ACCEPTANCE_MIN_SUSTAINED_REQUEST_COUNT must be a positive integer." >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_final_optimization_acceptance_$stamp"
mkdir -p "$run_dir"

python3 - "$run_dir" "$report_root" "$best_load_to_run_ratio" "$min_wall_delta_ratio" "$min_sustained_request_count" <<'PY'
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
best_load_to_run_ratio = float(sys.argv[3])
min_wall_delta_ratio = float(sys.argv[4])
min_sustained_request_count = int(sys.argv[5])
errors = []
warnings = []
checks = []


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


def add_check(name, ok, details):
    row = {
        "name": name,
        "ok": bool(ok),
        "details": details,
    }
    checks.append(row)
    if not ok:
        errors.append(f"{name} failed: {details}")


inventory_path, inventory = latest_json("dream7b_bpu_resplit_hbm_artifact_inventory_*/resplit_hbm_artifact_inventory_probe.json")
resplit_path, resplit = latest_json("dream7b_bpu_resplit_batch_telemetry_*/resplit_batch_telemetry_probe.json")
window_path, window = latest_json("dream7b_bpu_resplit_window_cost_*/resplit_window_cost_probe.json")
selected_path, selected = latest_json("dream7b_bpu_selected_pair_telemetry_*/selected_pair_telemetry_probe.json")
service_path, service = latest_json("dream7b_bpu_selected_pair_candidate_service_telemetry_*/systemd_telemetry_probe.json")
promotion_path, promotion = latest_json("dream7b_bpu_selected_pair_service_promotion_gate_*/selected_pair_service_promotion_gate_probe.json")
blocker_path, blocker = latest_json("dream7b_bpu_promotion_blocker_diagnosis_*/promotion_blocker_diagnosis_probe.json")
utilization_path, utilization = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
acceptance_path, acceptance = latest_json("dream7b_bpu_deployment_acceptance_*/deployment_acceptance_probe.json")
reload_path, reload = latest_json("dream7b_bpu_reload_optimization_*/reload_optimization_probe.json")
dream_oellm_path, dream_oellm = latest_json("dream7b_oellm_fullflow_feasibility_*/dream7b_oellm_fullflow_feasibility_probe.json")
qwen_path, qwen = latest_json("s100_official_qwen_fullflow_*/official_qwen_fullflow_probe.json")
deepseek_path, deepseek = latest_json("s100_official_deepseek7b_baseline_*/deepseek7b_baseline_probe.json")

evidence_paths = {
    "hbm_artifact_inventory": str(inventory_path) if inventory_path else "",
    "resplit_batch_telemetry": str(resplit_path) if resplit_path else "",
    "resplit_window_cost": str(window_path) if window_path else "",
    "selected_pair_telemetry": str(selected_path) if selected_path else "",
    "selected_pair_sustained_service_telemetry": str(service_path) if service_path else "",
    "selected_pair_service_promotion_gate": str(promotion_path) if promotion_path else "",
    "promotion_blocker_diagnosis": str(blocker_path) if blocker_path else "",
    "utilization_gap": str(utilization_path) if utilization_path else "",
    "deployment_acceptance": str(acceptance_path) if acceptance_path else "",
    "reload_optimization": str(reload_path) if reload_path else "",
    "dream_oellm_fullflow_feasibility": str(dream_oellm_path) if dream_oellm_path else "",
    "qwen_official_fullflow": str(qwen_path) if qwen_path else "",
    "deepseek7b_official_baseline": str(deepseek_path) if deepseek_path else "",
}

deployment_route_closed = (
    inventory.get("verdict") == "ok_dream7b_bpu_resplit_hbm_artifact_inventory_probe"
    and inventory.get("expected_hbm_count") == 8
    and inventory.get("existing_hbm_count") == 8
    and inventory.get("manifest_verified_count") == 8
    and resplit.get("verdict") == "ok_dream7b_bpu_resplit_batch_telemetry_probe"
    and int(resplit.get("batch_count") or 0) >= 16
    and (resplit.get("forward_metrics") or {}).get("window_execution_mode") in ("window-batch", "selected-pair-resident")
    and service.get("verdict") == "ok_dream7b_bpu_batch_queue_systemd_telemetry_probe"
    and service.get("service_name") == "dream7b-bpu-selected-pair-candidate.service"
    and promotion.get("live_services", {}).get("candidate_service_isolated_from_default") is True
)
add_check(
    "deployment_route_closed",
    deployment_route_closed,
    {
        "hbm_inventory_path": evidence_paths["hbm_artifact_inventory"],
        "resplit_batch_telemetry_path": evidence_paths["resplit_batch_telemetry"],
        "sustained_service_telemetry_path": evidence_paths["selected_pair_sustained_service_telemetry"],
        "expected_hbm_count": inventory.get("expected_hbm_count"),
        "existing_hbm_count": inventory.get("existing_hbm_count"),
        "manifest_verified_count": inventory.get("manifest_verified_count"),
        "batch_count": resplit.get("batch_count"),
        "candidate_service_isolated_from_default": promotion.get("live_services", {}).get("candidate_service_isolated_from_default"),
    },
)

selected_cmp = selected.get("comparison_to_default_runtime_telemetry") or {}
selected_single = selected.get("selected") or {}
reload_sustained = reload.get("sustained_service_candidate_metrics") or {}
promotion_metrics = promotion.get("metrics") or {}
blocker_deltas = blocker.get("metric_deltas") or {}
selected_pair_wall_delta_vs_resplit = safe_float(reload.get("selected_pair_candidate_metrics", {}).get("wall_delta_ratio_vs_resplit"))
sustained_wall_delta_vs_resplit = safe_float(reload_sustained.get("wall_delta_ratio_vs_resplit_per_request"), safe_float(promotion_metrics.get("wall_delta_ratio_vs_resplit_per_request")))
sustained_wall_delta_vs_default = safe_float(promotion_metrics.get("wall_delta_ratio_vs_default_systemd"))
resplit_load_to_run = safe_float((resplit.get("forward_metrics") or {}).get("load_to_run_ratio"))
sustained_load_to_run = safe_float(promotion_metrics.get("candidate_load_to_run_ratio"), safe_float(reload_sustained.get("load_to_run_ratio")))
selected_avg_bpu_delta_vs_resplit = safe_float(reload.get("selected_pair_candidate_metrics", {}).get("avg_bpu_delta_vs_resplit"))
sustained_request_count = int(service.get("processed_request_count") or 0)

substantial_improvement_observed = any(
    item is not None and item >= min_wall_delta_ratio
    for item in (selected_pair_wall_delta_vs_resplit, sustained_wall_delta_vs_resplit, sustained_wall_delta_vs_default)
) or (
    sustained_load_to_run is not None and sustained_load_to_run < best_load_to_run_ratio
) or (
    selected_avg_bpu_delta_vs_resplit is not None and selected_avg_bpu_delta_vs_resplit > 0
)
add_check(
    "performance_optimization_has_measured_gain",
    substantial_improvement_observed,
    {
        "selected_pair_wall_delta_ratio_vs_resplit": selected_pair_wall_delta_vs_resplit,
        "sustained_wall_delta_ratio_vs_resplit_per_request": sustained_wall_delta_vs_resplit,
        "sustained_wall_delta_ratio_vs_default_systemd": sustained_wall_delta_vs_default,
        "sustained_load_to_run_ratio": sustained_load_to_run,
        "best_load_to_run_ratio": best_load_to_run_ratio,
        "selected_pair_avg_bpu_delta_vs_resplit": selected_avg_bpu_delta_vs_resplit,
        "sustained_request_count": sustained_request_count,
    },
)

utilization_statement_compliant = (
    utilization.get("diagnosis") == "hbm_reload_dominated"
    and promotion.get("promotion_decision") == "block_default_service_replacement"
    and blocker.get("promotion_decision") == "keep_candidate_only_until_blockers_clear"
    and reload_sustained.get("default_service_replacement_decision") == "do_not_replace_default_service_yet"
    and substantial_improvement_observed
)
add_check(
    "tops_utilization_statement_compliant",
    utilization_statement_compliant,
    {
        "diagnosis": utilization.get("diagnosis"),
        "promotion_decision": promotion.get("promotion_decision"),
        "blocker_decision": blocker.get("promotion_decision"),
        "reload_default_service_replacement_decision": reload_sustained.get("default_service_replacement_decision"),
        "max_bpu_loading": resplit.get("max_bpu_loading"),
        "avg_bpu_loading": resplit.get("avg_bpu_loading"),
    },
)

promotion_gate_closed = (
    promotion.get("verdict") == "ok_dream7b_bpu_selected_pair_service_promotion_gate_probe"
    and promotion.get("promotion_allowed") is False
    and promotion.get("promotion_decision") == "block_default_service_replacement"
    and promotion.get("default_service_replaced") is False
    and isinstance(promotion.get("rollback_plan"), list)
    and any("restart dream7b-bpu-batch-queue.service" in item for item in promotion.get("rollback_plan", []))
)
add_check(
    "default_service_promotion_gate_closed",
    promotion_gate_closed,
    {
        "promotion_allowed": promotion.get("promotion_allowed"),
        "promotion_decision": promotion.get("promotion_decision"),
        "default_service_replaced": promotion.get("default_service_replaced"),
        "promotion_blockers": promotion.get("promotion_blockers"),
        "rollback_plan": promotion.get("rollback_plan"),
    },
)

dream_oellm_registry_missing = (
    dream_oellm.get("failure_stage") == "registry_missing"
    and dream_oellm.get("dream_registered_in_official_sdk") is False
    and dream_oellm.get("direct_oellm_migration_supported") is False
    and "required_adapter" in (dream_oellm.get("missing_adapter_evidence") or {})
)
add_check(
    "dream_official_oellm_route_concluded",
    dream_oellm_registry_missing,
    {
        "path": evidence_paths["dream_oellm_fullflow_feasibility"],
        "failure_stage": dream_oellm.get("failure_stage"),
        "dream_registered_in_official_sdk": dream_oellm.get("dream_registered_in_official_sdk"),
        "direct_oellm_migration_supported": dream_oellm.get("direct_oellm_migration_supported"),
        "missing_adapter_evidence": dream_oellm.get("missing_adapter_evidence"),
    },
)

qwen_fallback_verified = (
    qwen.get("runtime_completed") is True
    and qwen.get("runtime_returncode") == 0
    and qwen.get("memory_alloc_failure_observed") is False
)
deepseek_blocked = (
    deepseek.get("decision") == "official_7b_runtime_blocked_common_buffer"
    and deepseek.get("memory_alloc_failure_observed") is True
    and int(deepseek.get("bpu_alloc_request_bytes") or 0) == 7928846896
)
add_check(
    "official_fallback_routes_concluded",
    qwen_fallback_verified and deepseek_blocked,
    {
        "qwen_path": evidence_paths["qwen_official_fullflow"],
        "qwen_runtime_completed": qwen.get("runtime_completed"),
        "qwen_runtime_returncode": qwen.get("runtime_returncode"),
        "qwen_memory_alloc_failure_observed": qwen.get("memory_alloc_failure_observed"),
        "deepseek_path": evidence_paths["deepseek7b_official_baseline"],
        "deepseek_decision": deepseek.get("decision"),
        "deepseek_bpu_alloc_request_bytes": deepseek.get("bpu_alloc_request_bytes"),
    },
)

blocker_plan_available = (
    blocker.get("verdict") == "ok_dream7b_bpu_promotion_blocker_diagnosis_probe"
    and blocker.get("promotion_decision") == "keep_candidate_only_until_blockers_clear"
    and isinstance(blocker.get("next_optimization_candidates"), list)
    and len(blocker.get("next_optimization_candidates") or []) >= 2
)
add_check(
    "next_optimization_plan_available",
    blocker_plan_available,
    {
        "blocker_path": evidence_paths["promotion_blocker_diagnosis"],
        "promotion_decision": blocker.get("promotion_decision"),
        "next_optimization_candidates": [item.get("candidate") for item in blocker.get("next_optimization_candidates", [])],
    },
)

docs_consistency_external_required = True
final_goal_satisfied = not errors
if final_goal_satisfied:
    final_decision = "dream7b_bpu_optimized_candidate_complete_candidate_only"
    final_summary = "Dream 7B has a reproducible, accepted, rollback-gated BPU optimization candidate with measured wall-time improvement; default service replacement remains blocked by average BPU and load/run."
else:
    final_decision = "dream7b_bpu_optimization_goal_incomplete"
    final_summary = "One or more final acceptance requirements are not proven by current evidence."

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_final_optimization_acceptance_probe" if not errors else "failed_dream7b_final_optimization_acceptance_probe",
    "run_dir": str(run_dir),
    "report_root": str(report_root),
    "best_load_to_run_ratio": best_load_to_run_ratio,
    "min_wall_delta_ratio": min_wall_delta_ratio,
    "min_sustained_request_count": min_sustained_request_count,
    "evidence_paths": evidence_paths,
    "final_goal_satisfied": final_goal_satisfied,
    "final_decision": final_decision,
    "final_summary": final_summary,
    "docs_consistency_external_required": docs_consistency_external_required,
    "deployment_route_closed": deployment_route_closed,
    "substantial_improvement_observed": substantial_improvement_observed,
    "utilization_statement_compliant": utilization_statement_compliant,
    "promotion_gate_closed": promotion_gate_closed,
    "dream_oellm_registry_missing": dream_oellm_registry_missing,
    "qwen_fallback_verified": qwen_fallback_verified,
    "deepseek7b_blocked_common_buffer": deepseek_blocked,
    "candidate_service_only": promotion.get("promotion_allowed") is False,
    "default_service_replaced": promotion.get("default_service_replaced"),
    "metrics": {
        "resplit_load_to_run_ratio": resplit_load_to_run,
        "sustained_load_to_run_ratio": sustained_load_to_run,
        "selected_pair_wall_delta_ratio_vs_resplit": selected_pair_wall_delta_vs_resplit,
        "sustained_wall_delta_ratio_vs_resplit_per_request": sustained_wall_delta_vs_resplit,
        "sustained_wall_delta_ratio_vs_default_systemd": sustained_wall_delta_vs_default,
        "selected_pair_avg_bpu_delta_vs_resplit": selected_avg_bpu_delta_vs_resplit,
        "sustained_request_count": sustained_request_count,
        "resplit_avg_bpu_loading": safe_float(resplit.get("avg_bpu_loading")),
        "sustained_avg_bpu_loading": safe_float(service.get("avg_bpu_loading")),
    },
    "checks": checks,
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "final_optimization_acceptance_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B Final Optimization Acceptance",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- final_goal_satisfied: {payload['final_goal_satisfied']}",
    f"- final_decision: {payload['final_decision']}",
    f"- final_summary: {payload['final_summary']}",
    f"- docs_consistency_external_required: {payload['docs_consistency_external_required']}",
    "",
    "## Checks",
    "",
]
for check in checks:
    lines.append(f"- {check['name']}: ok={check['ok']}")
lines.extend(["", "## Metrics", ""])
for key, value in payload["metrics"].items():
    lines.append(f"- {key}: {value}")
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(run_dir / "final_optimization_acceptance_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "final_optimization_acceptance_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
