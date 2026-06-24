#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_tuning_decision_matrix_20260621.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_tuning_decision_matrix_20260621.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def observed_variant(group_order: dict[str, Any], label: str) -> dict[str, Any]:
    for row in group_order.get("observed_variants") or []:
        if row.get("label") == label:
            return row
    return {}


def top_capacity_candidate(planner: dict[str, Any]) -> dict[str, Any]:
    rows = planner.get("top_capacity_probe_candidates") or []
    return rows[0] if rows else {}


def compile_ready(readiness: dict[str, Any]) -> bool:
    return readiness.get("compile_ready") is True


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    group_order = read_json(args.group_order_json)
    planner = read_json(args.group_partition_json)
    scorecard = read_json(args.segment_scorecard_json)
    post_segment = read_json(args.post_segment_json)
    scheduler = read_json(args.scheduler_json)
    runtime_gate = read_json(args.runtime_gate_json)
    hidden_reuse = read_json(args.hidden_reuse_json)
    final_logits_leverage = read_json(args.final_logits_leverage_json)
    runtime_refactor = read_json(args.runtime_refactor_json)
    compile_readiness = read_json(args.compile_readiness_json)
    compile_capacity = read_json(args.compile_capacity_json)
    overlap = read_json(args.workstream_overlap_json)

    order_decision = group_order.get("decision") or {}
    planner_decision = planner.get("decision") or {}
    score_decision = scorecard.get("decision") or {}
    post_decision = post_segment.get("decision") or {}
    scheduler_decision = scheduler.get("decision") or {}
    runtime_decision = runtime_gate.get("decision") or {}
    hidden_decision = hidden_reuse.get("decision") or {}
    final_leverage = final_logits_leverage.get("leverage") or {}
    final_leverage_decision = final_logits_leverage.get("decision") or {}
    final_bpu_gap = final_logits_leverage.get("bpu_promotion_gap") or {}
    refactor_decision = runtime_refactor.get("decision") or {}
    refactor_backlog = runtime_refactor.get("backlog") or []
    refactor_rank1 = refactor_backlog[0] if refactor_backlog else {}
    capacity_top = top_capacity_candidate(planner)
    compile_recommendation = compile_capacity.get("recommendation") or {}
    overlap_decision = overlap.get("decision") or {}

    microbatch_major = observed_variant(group_order, "mb512_microbatch_major_same_ranges")
    g6_even = observed_variant(group_order, "mb512_segment_major_g6_even")
    g7_even = observed_variant(group_order, "mb512_segment_major_g7_even")
    final_isolated = observed_variant(group_order, "mb512_segment_major_final_isolated")

    matrix_rows = [
        {
            "lever": "inner_order",
            "current_policy": "segment-major",
            "candidate": "microbatch-major_same_ranges",
            "decision": "keep_segment_major",
            "allowed_now": False,
            "primary_evidence": {
                "candidate_delta_ms_per_request": microbatch_major.get(
                    "delta_ms_per_request_vs_baseline"
                ),
                "candidate_delta_avg_bpu": microbatch_major.get("delta_avg_bpu_vs_baseline"),
                "segment_major_preferred": order_decision.get(
                    "segment_major_preferred_over_microbatch_major"
                ),
            },
            "reason": "microbatch-major is slower than the mb512 segment-major 5-group baseline.",
        },
        {
            "lever": "group_count_mb512",
            "current_policy": "5_group_segment_major_default",
            "candidate": "6_or_7_group_boundary_sweeps",
            "decision": "keep_5_group_default",
            "allowed_now": False,
            "primary_evidence": {
                "g6_delta_ms_per_request": g6_even.get("delta_ms_per_request_vs_baseline"),
                "g7_delta_ms_per_request": g7_even.get("delta_ms_per_request_vs_baseline"),
                "no_observed_variant_beats_baseline": order_decision.get(
                    "no_observed_variant_beats_baseline"
                ),
                "post_segment_group_size_tuning_implication": post_decision.get(
                    "group_size_tuning_implication"
                ),
            },
            "reason": "observed group-count variants do not beat the 5-group baseline.",
        },
        {
            "lever": "final_logits_group_isolation",
            "current_policy": "final_logits_in_24:28_group",
            "candidate": "final_logits_singleton_group",
            "decision": "do_not_promote",
            "allowed_now": False,
            "primary_evidence": {
                "final_isolated_delta_ms_per_request": final_isolated.get(
                    "delta_ms_per_request_vs_baseline"
                ),
                "top_group_contains_final_logits": post_decision.get(
                    "top_group_contains_final_logits"
                ),
                "top_group_by_segment_total": post_decision.get("top_group_by_segment_total"),
            },
            "reason": "isolating final logits as a group was slower and the largest group total is not the final group.",
        },
        {
            "lever": "lower_peak_hbm_partition",
            "current_policy": "do_not_change_runtime_partition",
            "candidate": "g7_lower_peak_capacity_partition",
            "decision": "capacity_probe_only_after_memory_plan_changes",
            "allowed_now": False,
            "primary_evidence": {
                "candidate_group_ranges": capacity_top.get("group_ranges"),
                "peak_hbm_delta_pct_vs_baseline": capacity_top.get(
                    "peak_hbm_delta_pct_vs_baseline"
                ),
                "estimated_release_delta_ms_per_request": capacity_top.get(
                    "estimated_release_delta_ms_per_request"
                ),
                "run_new_partition_now": planner_decision.get("run_new_partition_now"),
            },
            "reason": "lower peak HBM is useful only as a capacity probe; observed nonbaseline runtime variants remain slower.",
        },
        {
            "lever": "microbatch_count",
            "current_policy": "do_not_extend_standard_sweeps",
            "candidate": "mb6144_or_higher_standard_sweep",
            "decision": "blocked_duplicate_or_capacity",
            "allowed_now": False,
            "primary_evidence": {
                "s100p_runtime_experiment_now": runtime_decision.get(
                    "s100p_runtime_experiment_now"
                ),
                "allowed_experiments": runtime_decision.get("allowed_experiments") or [],
                "runtime_gate_reason": runtime_decision.get("reason"),
                "workstream_standard_true_batch_runtime_blocked": overlap_decision.get(
                    "do_not_start_standard_true_batch_runtime_now"
                ),
            },
            "reason": "standard B=4 sweeps are already covered and the next nonduplicate candidate is last-token final logits.",
        },
        {
            "lever": "python_inter_segment_gap",
            "current_policy": "do_not_prioritize",
            "candidate": "reduce_python_gap_first",
            "decision": "deprioritize_until_final_logits_changes",
            "allowed_now": False,
            "primary_evidence": {
                "scheduler_primary_code_target": scheduler_decision.get("primary_code_target"),
                "deprioritize_python_inter_segment_gap_tuning": scheduler_decision.get(
                    "deprioritize_python_inter_segment_gap_tuning"
                ),
                "post_segment_next_code_target": post_decision.get("next_code_target"),
            },
            "reason": "measured scheduling gaps are far smaller than the final-logits excess.",
        },
        {
            "lever": "hidden_materialize_buffer_reuse",
            "current_policy": "preallocate_hidden_off",
            "candidate": "current_preallocate_hidden_path",
            "decision": "reject_current_implementation",
            "allowed_now": False,
            "primary_evidence": {
                "hidden_buffer_reuse_default": hidden_decision.get("hidden_buffer_reuse_default"),
                "preallocate_hidden_experimental_flag_only": hidden_decision.get(
                    "preallocate_hidden_experimental_flag_only"
                ),
                "reuse_buffer_implementation_measured_slower": hidden_decision.get(
                    "reuse_buffer_implementation_measured_slower"
                ),
            },
            "reason": "the measured preallocate-hidden implementation worsened latency.",
        },
        {
            "lever": "final_logits_output_avoidance",
            "current_policy": "research_candidate_only",
            "candidate": "seg27_28_last_token_logits",
            "decision": "primary_next_candidate_but_compile_blocked",
            "allowed_now": False,
            "primary_evidence": {
                "primary_runtime_lever": score_decision.get("primary_runtime_lever"),
                "next_runtime_candidate": runtime_decision.get(
                    "next_nonduplicate_runtime_candidate"
                ),
                "runtime_refactor_primary_target": refactor_decision.get(
                    "primary_runtime_refactor_target"
                ),
                "projected_saved_ms_per_request": final_leverage.get(
                    "projection_saved_ms_per_request"
                ),
                "projection_capture_of_final_excess_pct": final_leverage.get(
                    "projection_capture_of_final_excess_pct"
                ),
                "latest_projected_latency_reduction_pct": final_leverage.get(
                    "latest_projected_latency_reduction_pct"
                ),
                "latest_nonzero_shortfall_points": final_bpu_gap.get(
                    "latest_nonzero_shortfall_points"
                ),
                "projection_is_not_bpu_promotion_proof": final_leverage_decision.get(
                    "projection_is_not_bpu_promotion_proof"
                ),
                "do_not_promote_without_runtime_result": final_leverage_decision.get(
                    "do_not_promote_without_runtime_result"
                ),
                "do_not_run_standard_group_or_inner_order_sweeps": final_leverage_decision.get(
                    "do_not_run_standard_group_or_inner_order_sweeps"
                ),
                "compile_ready": compile_readiness.get("compile_ready"),
                "runtime_validation_ready": compile_readiness.get("runtime_validation_ready"),
                "compile_do_not_start_compile_now": compile_recommendation.get(
                    "do_not_start_compile_now"
                ),
            },
            "reason": "final logits is the right next code target with a material latency projection, but it is not BPU-promotion proof and local compile/pagefile plus remote manifest gates still block it.",
        },
        {
            "lever": "queue_batch_production_default",
            "current_policy": "queue_batch_default",
            "candidate": "promote_true_batch_b4",
            "decision": "do_not_promote_true_batch",
            "allowed_now": False,
            "primary_evidence": {
                "queue_batch_service_remains_default": runtime_decision.get(
                    "queue_batch_service_remains_default"
                ),
                "do_not_promote_true_batch": runtime_decision.get("do_not_promote_true_batch"),
                "queue_batch_work_duplicates_prior_true_batch_rental": overlap_decision.get(
                    "queue_batch_work_duplicates_prior_true_batch_rental"
                ),
            },
            "reason": "queue-batch remains the stable production baseline; B=4 true-batch is a research artifact.",
        },
    ]
    blockers = []
    for row in matrix_rows:
        if row["lever"] != "final_logits_output_avoidance" and row["allowed_now"]:
            blockers.append(f"unexpected_allowed:{row['lever']}")
    if compile_ready(compile_readiness):
        blockers.append("last_token_compile_unexpectedly_ready_without_runtime_validation")
    if runtime_decision.get("allowed_experiments"):
        blockers.append("runtime_gate_allows_experiments")
    if refactor_decision.get("primary_runtime_refactor_target") != "final_logits_last_token_path":
        blockers.append("runtime_refactor_primary_target_mismatch")
    if refactor_decision.get("rank1_projected_saved_ms_per_request") != final_leverage.get(
        "projection_saved_ms_per_request"
    ):
        blockers.append("runtime_refactor_leverage_projection_mismatch")
    if final_leverage_decision.get("projection_is_not_bpu_promotion_proof") is not True:
        blockers.append("final_logits_leverage_promotion_guard_missing")
    if final_leverage_decision.get("do_not_run_standard_group_or_inner_order_sweeps") is not True:
        blockers.append("final_logits_standard_sweep_guard_missing")
    if (refactor_rank1.get("evidence") or {}).get(
        "do_not_run_standard_group_or_inner_order_sweeps"
    ) is not True:
        blockers.append("runtime_refactor_standard_sweep_guard_missing")

    decision = {
        "recommended_runtime_default": "5_group_segment_major_queue_batch_default",
        "recommended_true_batch_b4_policy": "do_not_run_standard_sweeps_now",
        "preferred_group_policy": "keep_existing_5_group_segment_major_default",
        "preferred_inner_order": "segment-major",
        "primary_code_target": "seg27_28_last_token_logits_or_output_avoidance",
        "secondary_research_target": "alternative_hidden_materialize_avoidance_without_preallocated_copyto",
        "primary_code_target_projected_saved_ms_per_request": final_leverage.get(
            "projection_saved_ms_per_request"
        ),
        "primary_code_target_not_bpu_promotion_proof": final_leverage_decision.get(
            "projection_is_not_bpu_promotion_proof"
        ),
        "standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage": final_leverage_decision.get(
            "do_not_run_standard_group_or_inner_order_sweeps"
        ),
        "next_s100p_runtime_experiment_allowed": False,
        "next_compile_allowed": False,
    }
    verdict = "ok_dream7b_b4_tuning_decision_matrix" if not blockers else "warning_dream7b_b4_tuning_decision_matrix"
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "source_paths": {
            "group_order": str(args.group_order_json),
            "group_partition": str(args.group_partition_json),
            "segment_scorecard": str(args.segment_scorecard_json),
            "post_segment": str(args.post_segment_json),
            "scheduler": str(args.scheduler_json),
            "runtime_gate": str(args.runtime_gate_json),
            "hidden_reuse": str(args.hidden_reuse_json),
            "final_logits_leverage": str(args.final_logits_leverage_json),
            "runtime_refactor": str(args.runtime_refactor_json),
            "compile_readiness": str(args.compile_readiness_json),
            "compile_capacity": str(args.compile_capacity_json),
            "workstream_overlap": str(args.workstream_overlap_json),
        },
        "matrix_rows": matrix_rows,
        "decision": decision,
        "blockers": blockers,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    decision = payload["decision"]
    lines = [
        "# Dream7B B=4 Tuning Decision Matrix",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- recommended_runtime_default: `{decision['recommended_runtime_default']}`",
        f"- preferred_group_policy: `{decision['preferred_group_policy']}`",
        f"- preferred_inner_order: `{decision['preferred_inner_order']}`",
        f"- primary_code_target: `{decision['primary_code_target']}`",
        f"- primary_code_target_projected_saved_ms_per_request: `{decision['primary_code_target_projected_saved_ms_per_request']}`",
        f"- primary_code_target_not_bpu_promotion_proof: `{decision['primary_code_target_not_bpu_promotion_proof']}`",
        f"- standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage: `{decision['standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage']}`",
        f"- next_s100p_runtime_experiment_allowed: `{decision['next_s100p_runtime_experiment_allowed']}`",
        f"- next_compile_allowed: `{decision['next_compile_allowed']}`",
        "",
        "| lever | candidate | decision | allowed_now | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["matrix_rows"]:
        lines.append(
            f"| {row['lever']} | {row['candidate']} | {row['decision']} | "
            f"{row['allowed_now']} | {row['reason']} |"
        )
    lines.extend(["", "## Evidence", ""])
    for row in payload["matrix_rows"]:
        lines.append(f"### {row['lever']}")
        lines.append("")
        for key, value in row["primary_evidence"].items():
            lines.append(f"- {key}: `{value}`")
        lines.append("")
    if payload["blockers"]:
        lines.extend(["## Blockers", ""])
        lines.extend(f"- {item}" for item in payload["blockers"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a non-executing B=4 tuning decision matrix from existing Dream7B telemetry."
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--snapshot-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--group-order-json", type=Path, default=DEFAULT_ROOT / "dream7b_b4_group_order_candidate_analysis_20260620.json")
    parser.add_argument("--group-partition-json", type=Path, default=DEFAULT_ROOT / "dream7b_b4_group_partition_planner_20260620.json")
    parser.add_argument("--segment-scorecard-json", type=Path, default=DEFAULT_ROOT / "dream7b_b4_segment_bottleneck_scorecard_20260620.json")
    parser.add_argument("--post-segment-json", type=Path, default=DEFAULT_ROOT / "dream7b_b4_post_instrumentation_segment_attribution_20260621.json")
    parser.add_argument("--scheduler-json", type=Path, default=DEFAULT_ROOT / "dream7b_b4_scheduler_overhead_budget_20260620.json")
    parser.add_argument("--runtime-gate-json", type=Path, default=DEFAULT_ROOT / "dream7b_b4_runtime_experiment_gate_20260620.json")
    parser.add_argument("--hidden-reuse-json", type=Path, default=DEFAULT_ROOT / "dream7b_b4_hidden_buffer_reuse_decision_20260621.json")
    parser.add_argument("--final-logits-leverage-json", type=Path, default=DEFAULT_ROOT / "dream7b_b4_final_logits_leverage_model_20260621.json")
    parser.add_argument("--runtime-refactor-json", type=Path, default=DEFAULT_ROOT / "dream7b_b4_runtime_refactor_backlog_20260621.json")
    parser.add_argument("--compile-readiness-json", type=Path, default=DEFAULT_ROOT / "dream7b_b4_last_token_compile_readiness_20260619.json")
    parser.add_argument("--compile-capacity-json", type=Path, default=DEFAULT_ROOT / "dream7b_b4_compile_capacity_plan_20260619.json")
    parser.add_argument("--workstream-overlap-json", type=Path, default=Path("tmp/product_guardrail_snapshots/dream7b_workstream_overlap_audit_20260621-021743/dream7b_workstream_overlap_audit.json"))
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
