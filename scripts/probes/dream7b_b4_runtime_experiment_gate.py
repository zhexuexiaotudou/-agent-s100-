#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ANALYSIS_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_SNAPSHOT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_OUT_JSON = DEFAULT_ANALYSIS_ROOT / "dream7b_b4_runtime_experiment_gate_20260620.json"
DEFAULT_OUT_MD = DEFAULT_ANALYSIS_ROOT / "dream7b_b4_runtime_experiment_gate_20260620.md"


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_report_time(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def latest_json(root: Path, filename: str) -> Path | None:
    if not root.exists():
        return None
    candidates = [path for path in root.rglob(filename) if path.is_file()]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda path: (
            parse_report_time((read_json(path) or {}).get("generated_at")),
            path.stat().st_mtime,
            str(path),
        ),
    )


def get(payload: dict[str, Any], path: list[str], default: Any = None) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return default
        value = value.get(key)
    return default if value is None else value


def without_payload_path(path: Path | None) -> str | None:
    return str(path) if path else None


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    analysis_root = args.analysis_root
    snapshot_root = args.snapshot_root

    inventory_path = analysis_root / "dream7b_true_batch_nas_inventory_20260620.json"
    planner_path = analysis_root / "dream7b_b4_group_partition_planner_20260620.json"
    compare_path = analysis_root / "dream7b_b4_last_token_validation_compare_20260620.json"
    compile_readiness_path = analysis_root / "dream7b_b4_last_token_compile_readiness_20260619.json"
    experiment_gate_path = analysis_root / "dream7b_b4_last_token_experiment_gate_20260620.json"
    validation_plan_path = analysis_root / "dream7b_b4_last_token_runtime_validation_plan_20260620.json"
    final_logits_leverage_path = analysis_root / "dream7b_b4_final_logits_leverage_model_20260621.json"
    runtime_refactor_path = analysis_root / "dream7b_b4_runtime_refactor_backlog_20260621.json"
    tuning_matrix_path = analysis_root / "dream7b_b4_tuning_decision_matrix_20260621.json"
    per_run_evidence_matrix_path = (
        analysis_root / "dream7b_b4_per_run_evidence_matrix_20260622.json"
    )
    post_instrumentation_gate_path = (
        analysis_root / "dream7b_b4_post_instrumentation_telemetry_gate_20260621.json"
    )
    post_instrumentation_segment_path = (
        analysis_root / "dream7b_b4_post_instrumentation_segment_attribution_20260621.json"
    )
    freshness_path = snapshot_root / "dream7b_default_service_freshness_gate_latest.json"
    slo_path = latest_json(snapshot_root, "operational_slo_rollup_contract.json")
    product_path = latest_json(snapshot_root, "dream7b_product_decision_packet.json")

    inventory = read_json(inventory_path)
    planner = read_json(planner_path)
    compare = read_json(compare_path)
    compile_readiness = read_json(compile_readiness_path)
    experiment_gate = read_json(experiment_gate_path)
    validation_plan = read_json(validation_plan_path)
    final_logits_leverage = read_json(final_logits_leverage_path)
    runtime_refactor = read_json(runtime_refactor_path)
    tuning_matrix = read_json(tuning_matrix_path)
    per_run_evidence_matrix = read_json(per_run_evidence_matrix_path)
    post_instrumentation_gate = read_json(post_instrumentation_gate_path)
    post_instrumentation_segment = read_json(post_instrumentation_segment_path)
    freshness = read_json(freshness_path)
    slo = read_json(slo_path)
    product = read_json(product_path)

    inventory_decision = inventory.get("decision") or {}
    local_coverage = inventory.get("local_coverage") or {}
    remote_inventory = inventory.get("remote") or {}
    planner_decision = planner.get("decision") or {}
    compare_decision = compare.get("decision") or {}
    experiment_summary = experiment_gate.get("summary") or {}
    validation_readiness = validation_plan.get("readiness") or {}
    final_leverage = final_logits_leverage.get("leverage") or {}
    final_leverage_decision = final_logits_leverage.get("decision") or {}
    runtime_refactor_decision = runtime_refactor.get("decision") or {}
    tuning_decision = tuning_matrix.get("decision") or {}
    per_run_summary = per_run_evidence_matrix.get("summary") or {}
    per_run_findings = per_run_evidence_matrix.get("findings") or {}
    per_run_admission = per_run_findings.get("admission") or {}
    per_run_audit = per_run_evidence_matrix.get("audit") or {}
    post_instrumentation_decision = post_instrumentation_gate.get("decision") or {}
    post_instrumentation_next = post_instrumentation_decision.get("next_measurement") or {}
    post_segment_decision = post_instrumentation_segment.get("decision") or {}
    freshness_decision = freshness.get("decision") or {}
    freshness_checks = freshness.get("checks") or {}
    slo_contracts = {item.get("key"): item for item in slo.get("contracts") or []}
    slo_freshness = slo_contracts.get("dream7b_default_service_freshness_gate") or {}

    standard_coverage = {
        "nas_b4_group_major_report_count": remote_inventory.get("b4_group_major_report_count"),
        "local_b4_json_count": local_coverage.get("local_b4_json_count"),
        "successful_b4_runs": local_coverage.get("successful_count"),
        "failed_capacity_probes": local_coverage.get("failed_count"),
        "by_microbatch_count": local_coverage.get("by_microbatch_count") or {},
        "by_group_count": local_coverage.get("by_group_count") or {},
        "has_mb512_segment_major_5_group": local_coverage.get("has_mb512_segment_major_5_group"),
        "has_mb512_microbatch_major": local_coverage.get("has_mb512_microbatch_major"),
        "has_mb512_nonbaseline_group_splits": local_coverage.get("has_mb512_nonbaseline_group_splits"),
        "has_gap_field_capacity_failures": local_coverage.get("has_gap_field_capacity_failures"),
        "remote_local_count_match": inventory_decision.get("b4_remote_local_count_match"),
        "run_more_standard_b4_runtime_sweeps_now": inventory_decision.get(
            "run_more_standard_b4_runtime_sweeps_now"
        ),
    }
    standard_sweeps_already_covered = all(
        standard_coverage.get(key) is True
        for key in [
            "has_mb512_segment_major_5_group",
            "has_mb512_microbatch_major",
            "has_mb512_nonbaseline_group_splits",
            "has_gap_field_capacity_failures",
            "remote_local_count_match",
        ]
    ) and standard_coverage.get("run_more_standard_b4_runtime_sweeps_now") is False
    post_segment_blocks_standard_group_sweeps = (
        post_instrumentation_segment.get("verdict")
        == "ok_dream7b_b4_post_instrumentation_segment_attribution"
        and post_segment_decision.get("do_not_run_more_standard_b4_group_order_sweeps_now")
        is True
        and post_segment_decision.get("group_size_tuning_implication")
        == "keep_existing_5_group_segment_major_default"
        and post_segment_decision.get("inner_order_tuning_implication") == "keep_segment_major"
    )
    final_logits_leverage_gate_ready = (
        final_logits_leverage.get("verdict") == "ok_dream7b_b4_final_logits_leverage_model"
        and final_leverage_decision.get("projection_is_not_bpu_promotion_proof") is True
        and final_leverage_decision.get("do_not_promote_without_runtime_result") is True
        and final_leverage_decision.get("do_not_run_standard_group_or_inner_order_sweeps")
        is True
    )
    runtime_refactor_gate_ready = (
        runtime_refactor.get("verdict") == "ok_dream7b_b4_runtime_refactor_backlog"
        and runtime_refactor_decision.get("primary_runtime_refactor_target")
        == "final_logits_last_token_path"
        and runtime_refactor_decision.get("rank1_projected_saved_ms_per_request")
        == final_leverage.get("projection_saved_ms_per_request")
        and runtime_refactor_decision.get("rank1_projection_is_not_bpu_promotion_proof")
        is True
        and runtime_refactor_decision.get("rank1_blocks_standard_group_or_inner_order_sweeps")
        is True
    )
    tuning_matrix_gate_ready = (
        tuning_matrix.get("verdict") == "ok_dream7b_b4_tuning_decision_matrix"
        and tuning_decision.get("primary_code_target_projected_saved_ms_per_request")
        == final_leverage.get("projection_saved_ms_per_request")
        and tuning_decision.get("primary_code_target_not_bpu_promotion_proof") is True
        and tuning_decision.get(
            "standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage"
        )
        is True
        and tuning_decision.get("next_s100p_runtime_experiment_allowed") is False
        and tuning_decision.get("next_compile_allowed") is False
    )
    per_run_matrix_gate_ready = (
        per_run_evidence_matrix.get("verdict") == "ok_dream7b_b4_per_run_evidence_matrix"
        and not (per_run_evidence_matrix.get("failed_checks") or [])
        and int(per_run_summary.get("run_count") or 0) >= 20
        and int(per_run_summary.get("successful_run_count") or 0) >= 19
        and int(per_run_summary.get("failed_run_count") or 0) >= 1
        and per_run_summary.get("most_common_top_segment") == "seg27_final_logits"
        and float(per_run_summary.get("most_common_top_segment_rate") or 0.0) == 1.0
        and per_run_summary.get("standard_b4_runtime_sweep_status")
        == "blocked_duplicate"
        and per_run_summary.get("run_more_standard_group_or_inner_order_sweeps_now")
        is False
        and per_run_admission.get("would_start_runtime") is False
        and per_run_admission.get("would_start_compile") is False
        and per_run_audit.get("remote_access_performed") is False
        and per_run_audit.get("runtime_started") is False
        and per_run_audit.get("compile_started") is False
    )
    admission_evidence_ready = (
        final_logits_leverage_gate_ready
        and runtime_refactor_gate_ready
        and tuning_matrix_gate_ready
        and per_run_matrix_gate_ready
    )

    service_gate_ready = (
        freshness.get("verdict") == "ok_dream7b_default_service_freshness_gate"
        and not freshness.get("failed_checks")
        and freshness_decision.get("queue_batch_service_remains_default") is True
        and freshness_decision.get("do_not_promote_true_batch") is True
        and freshness_checks.get("nas_inventory_prevents_duplicate_sweeps") is True
        and slo_freshness.get("accepted") is True
    )

    candidate_exists = get(compare, ["candidate", "exists"], False) is True
    last_token_compile_ready = compile_readiness.get("compile_ready") is True
    last_token_manifest_ready = validation_readiness.get("manifest_ready") is True
    last_token_validation_ready = validation_readiness.get("validation_ready") is True
    last_token_experiment_ready = experiment_summary.get("experiment_ready") is True
    last_token_compare_continue = (
        compare.get("verdict")
        == "ok_dream7b_b4_last_token_validation_compare_continue_runtime_validation"
    )
    last_token_mb512_validation_now = (
        service_gate_ready
        and admission_evidence_ready
        and last_token_compile_ready
        and last_token_manifest_ready
        and last_token_validation_ready
        and last_token_experiment_ready
        and not candidate_exists
    )

    capacity_partition_probe_now = (
        service_gate_ready
        and admission_evidence_ready
        and planner_decision.get("run_new_partition_now") is True
        and not post_segment_blocks_standard_group_sweeps
        and not last_token_mb512_validation_now
    )
    post_instrumentation_baseline_measurement_now = (
        service_gate_ready
        and admission_evidence_ready
        and post_instrumentation_decision.get(
            "allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available"
        )
        is True
        and post_instrumentation_decision.get("post_instrumentation_telemetry_ready")
        is False
        and post_instrumentation_decision.get("run_more_standard_b4_runtime_sweeps_now")
        is False
    )
    standard_s100p_runtime_now = (
        service_gate_ready
        and admission_evidence_ready
        and not standard_sweeps_already_covered
        and not post_segment_blocks_standard_group_sweeps
        and inventory_decision.get("run_more_standard_b4_runtime_sweeps_now") is True
    )
    run_s100p_experiment_now = (
        standard_s100p_runtime_now
        or last_token_mb512_validation_now
        or capacity_partition_probe_now
        or post_instrumentation_baseline_measurement_now
    )

    blockers: list[str] = []
    if not service_gate_ready:
        blockers.append("default_service_or_slo_gate_not_ready")
    if not final_logits_leverage_gate_ready:
        blockers.append("final_logits_leverage_gate_not_ready")
    if not runtime_refactor_gate_ready:
        blockers.append("runtime_refactor_gate_not_aligned_with_leverage")
    if not tuning_matrix_gate_ready:
        blockers.append("tuning_matrix_gate_not_aligned_with_leverage")
    if not per_run_matrix_gate_ready:
        blockers.append("per_run_evidence_matrix_gate_not_ready")
    if standard_sweeps_already_covered:
        blockers.append("standard_b4_sweeps_already_covered_by_nas_and_local_inventory")
    if not last_token_compile_ready:
        blockers.append("last_token_compile_not_ready")
    if not last_token_manifest_ready:
        blockers.append("last_token_manifest_not_ready")
    if not last_token_validation_ready:
        blockers.append("last_token_runtime_validation_not_ready")
    if candidate_exists and not last_token_compare_continue:
        blockers.append("last_token_candidate_exists_but_compare_gate_not_clear")
    if planner_decision.get("run_new_partition_now") is not True:
        blockers.append("group_partition_planner_deprioritizes_new_partition_run")
    if post_segment_blocks_standard_group_sweeps:
        blockers.append("post_instrumentation_segment_attribution_blocks_group_order_sweeps")
    if post_instrumentation_baseline_measurement_now:
        blockers.append(
            "post_instrumentation_baseline_measurement_allowed_but_not_started_by_gate"
        )

    duplicate_stop_rules = list(inventory_decision.get("duplicate_stop_rules") or [])
    if per_run_summary.get("standard_b4_runtime_sweep_status") == "blocked_duplicate":
        duplicate_stop_rules.append(
            "per_run_matrix_marks_standard_b4_runtime_sweep_blocked_duplicate"
        )

    allowed_experiments = []
    if standard_s100p_runtime_now:
        allowed_experiments.append("standard_b4_runtime_sweep")
    if last_token_mb512_validation_now:
        allowed_experiments.append("mb512_segment_major_last_token_validation")
    if capacity_partition_probe_now:
        allowed_experiments.append("capacity_partition_probe")
    if post_instrumentation_baseline_measurement_now:
        allowed_experiments.append("post_instrumentation_baseline_measurement")

    decision = {
        "s100p_runtime_experiment_now": run_s100p_experiment_now,
        "allowed_experiments": allowed_experiments,
        "run_standard_b4_sweeps_now": standard_s100p_runtime_now,
        "run_last_token_mb512_validation_now": last_token_mb512_validation_now,
        "run_capacity_partition_probe_now": capacity_partition_probe_now,
        "run_post_instrumentation_baseline_measurement_now": post_instrumentation_baseline_measurement_now,
        "queue_batch_service_remains_default": freshness_decision.get(
            "queue_batch_service_remains_default"
        ),
        "do_not_promote_true_batch": freshness_decision.get("do_not_promote_true_batch"),
        "next_nonduplicate_runtime_candidate": (
            "post_instrumentation_mb512_baseline_measurement"
            if post_instrumentation_baseline_measurement_now
            else "seg27_28_last_token_logits"
        ),
        "post_instrumentation_measurement_command": post_instrumentation_next.get("command"),
        "reason": (
            "post_instrumentation_baseline_measurement_is_allowed_but_gate_does_not_auto_start_runtime"
            if post_instrumentation_baseline_measurement_now
            else "no_s100p_runtime_now_standard_sweeps_are_duplicates_and_last_token_candidate_is_not_ready"
            if not run_s100p_experiment_now
            else "s100p_runtime_gate_open_for_allowed_experiments"
        ),
    }
    verdict = (
        "ok_dream7b_b4_runtime_experiment_gate_ready_to_run"
        if run_s100p_experiment_now
        else "blocked_dream7b_b4_runtime_experiment_gate_no_s100p_run_now"
    )

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "source_paths": {
            "true_batch_nas_inventory": without_payload_path(inventory_path),
            "group_partition_planner": without_payload_path(planner_path),
            "last_token_validation_compare": without_payload_path(compare_path),
            "last_token_compile_readiness": without_payload_path(compile_readiness_path),
            "last_token_experiment_gate": without_payload_path(experiment_gate_path),
            "last_token_runtime_validation_plan": without_payload_path(validation_plan_path),
            "final_logits_leverage": without_payload_path(final_logits_leverage_path),
            "runtime_refactor_backlog": without_payload_path(runtime_refactor_path),
            "tuning_decision_matrix": without_payload_path(tuning_matrix_path),
            "per_run_evidence_matrix": without_payload_path(per_run_evidence_matrix_path),
            "post_instrumentation_telemetry_gate": without_payload_path(
                post_instrumentation_gate_path
            ),
            "post_instrumentation_segment_attribution": without_payload_path(
                post_instrumentation_segment_path
            ),
            "default_service_freshness_gate": without_payload_path(freshness_path),
            "operational_slo_rollup": without_payload_path(slo_path),
            "product_decision_packet": without_payload_path(product_path),
        },
        "standard_b4_coverage": standard_coverage,
        "service_gate": {
            "ready": service_gate_ready,
            "freshness_verdict": freshness.get("verdict"),
            "freshness_failed_checks": freshness.get("failed_checks") or [],
            "slo_verdict": slo.get("verdict"),
            "slo_freshness_required": slo_freshness.get("required"),
            "slo_freshness_accepted": slo_freshness.get("accepted"),
            "product_verdict": product.get("verdict"),
        },
        "admission_evidence": {
            "ready": admission_evidence_ready,
            "final_logits_leverage_gate_ready": final_logits_leverage_gate_ready,
            "runtime_refactor_gate_ready": runtime_refactor_gate_ready,
            "tuning_matrix_gate_ready": tuning_matrix_gate_ready,
            "projected_saved_ms_per_request": final_leverage.get(
                "projection_saved_ms_per_request"
            ),
            "projection_is_not_bpu_promotion_proof": final_leverage_decision.get(
                "projection_is_not_bpu_promotion_proof"
            ),
            "do_not_promote_without_runtime_result": final_leverage_decision.get(
                "do_not_promote_without_runtime_result"
            ),
            "standard_group_or_inner_order_sweeps_blocked": final_leverage_decision.get(
                "do_not_run_standard_group_or_inner_order_sweeps"
            ),
            "runtime_refactor_primary_target": runtime_refactor_decision.get(
                "primary_runtime_refactor_target"
            ),
            "tuning_primary_code_target": tuning_decision.get("primary_code_target"),
            "per_run_matrix_gate_ready": per_run_matrix_gate_ready,
            "per_run_matrix_verdict": per_run_evidence_matrix.get("verdict"),
            "per_run_matrix_run_count": per_run_summary.get("run_count"),
            "per_run_matrix_successful_run_count": per_run_summary.get(
                "successful_run_count"
            ),
            "per_run_matrix_failed_run_count": per_run_summary.get("failed_run_count"),
            "per_run_matrix_top_segment": per_run_summary.get("most_common_top_segment"),
            "per_run_matrix_top_segment_rate": per_run_summary.get(
                "most_common_top_segment_rate"
            ),
            "per_run_matrix_standard_sweep_status": per_run_summary.get(
                "standard_b4_runtime_sweep_status"
            ),
            "per_run_matrix_run_more_standard_group_or_inner_order_sweeps_now": per_run_summary.get(
                "run_more_standard_group_or_inner_order_sweeps_now"
            ),
            "per_run_matrix_next_nonduplicate_runtime_candidate": per_run_summary.get(
                "next_nonduplicate_runtime_candidate"
            ),
        },
        "per_run_evidence_matrix": {
            "verdict": per_run_evidence_matrix.get("verdict"),
            "gate_ready": per_run_matrix_gate_ready,
            "run_count": per_run_summary.get("run_count"),
            "successful_run_count": per_run_summary.get("successful_run_count"),
            "failed_run_count": per_run_summary.get("failed_run_count"),
            "most_common_top_segment": per_run_summary.get("most_common_top_segment"),
            "most_common_top_segment_rate": per_run_summary.get(
                "most_common_top_segment_rate"
            ),
            "standard_b4_runtime_sweep_status": per_run_summary.get(
                "standard_b4_runtime_sweep_status"
            ),
            "run_more_standard_group_or_inner_order_sweeps_now": per_run_summary.get(
                "run_more_standard_group_or_inner_order_sweeps_now"
            ),
            "next_nonduplicate_runtime_candidate": per_run_summary.get(
                "next_nonduplicate_runtime_candidate"
            ),
            "would_start_runtime": per_run_admission.get("would_start_runtime"),
            "would_start_compile": per_run_admission.get("would_start_compile"),
        },
        "last_token_candidate": {
            "compile_ready": last_token_compile_ready,
            "manifest_ready": last_token_manifest_ready,
            "runtime_validation_ready": last_token_validation_ready,
            "experiment_ready": last_token_experiment_ready,
            "candidate_result_exists": candidate_exists,
            "validation_compare_verdict": compare.get("verdict"),
            "validation_compare_decision": compare_decision.get("decision"),
            "compile_blockers": compile_readiness.get("blockers") or [],
            "experiment_gate_blockers": experiment_summary.get("gate_blockers") or [],
            "runtime_validation_blockers": validation_readiness.get("blockers") or [],
        },
        "partition_candidate": {
            "planner_verdict": planner.get("verdict"),
            "candidate_count": get(planner, ["inputs", "candidate_count"]),
            "run_new_partition_now": planner_decision.get("run_new_partition_now"),
            "only_probe_if_memory_plan_changes": planner_decision.get(
                "only_probe_if_memory_plan_changes"
            ),
            "top_capacity_probe": (planner.get("top_capacity_probe_candidates") or [{}])[0],
            "reason": planner_decision.get("reason"),
        },
        "post_instrumentation_measurement": {
            "gate_verdict": post_instrumentation_gate.get("verdict"),
            "post_instrumentation_telemetry_ready": post_instrumentation_decision.get(
                "post_instrumentation_telemetry_ready"
            ),
            "input_output_overhead_quantified": post_instrumentation_decision.get(
                "input_output_overhead_quantified"
            ),
            "run_more_standard_b4_runtime_sweeps_now": post_instrumentation_decision.get(
                "run_more_standard_b4_runtime_sweeps_now"
            ),
            "allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available": post_instrumentation_decision.get(
                "allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available"
            ),
            "next_measurement": post_instrumentation_next,
        },
        "post_instrumentation_segment_attribution": {
            "verdict": post_instrumentation_segment.get("verdict"),
            "primary_single_segment_bottleneck": post_segment_decision.get(
                "primary_single_segment_bottleneck"
            ),
            "final_logits_compute_still_primary": post_segment_decision.get(
                "final_logits_compute_still_primary"
            ),
            "top_group_by_segment_total": post_segment_decision.get(
                "top_group_by_segment_total"
            ),
            "top_group_contains_final_logits": post_segment_decision.get(
                "top_group_contains_final_logits"
            ),
            "group_size_tuning_implication": post_segment_decision.get(
                "group_size_tuning_implication"
            ),
            "inner_order_tuning_implication": post_segment_decision.get(
                "inner_order_tuning_implication"
            ),
            "do_not_run_more_standard_b4_group_order_sweeps_now": post_segment_decision.get(
                "do_not_run_more_standard_b4_group_order_sweeps_now"
            ),
            "blocks_standard_group_sweeps": post_segment_blocks_standard_group_sweeps,
        },
        "duplicate_stop_rules": duplicate_stop_rules,
        "remaining_nonduplicate_work": inventory_decision.get("remaining_nonduplicate_work") or [],
        "blockers": blockers,
        "decision": decision,
        "audit": {
            "runtime_started": False,
            "compile_started": False,
            "service_restarted": False,
            "remote_write_performed": False,
            "local_writes": "JSON/Markdown runtime experiment gate only",
        },
    }


def write_report(payload: dict[str, Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    decision = payload["decision"]
    standard = payload["standard_b4_coverage"]
    service = payload["service_gate"]
    admission = payload["admission_evidence"]
    per_run = payload["per_run_evidence_matrix"]
    last_token = payload["last_token_candidate"]
    partition = payload["partition_candidate"]
    post_segment = payload["post_instrumentation_segment_attribution"]
    lines = [
        "# Dream7B B=4 Runtime Experiment Gate",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- s100p_runtime_experiment_now: `{decision['s100p_runtime_experiment_now']}`",
        f"- allowed_experiments: `{decision['allowed_experiments']}`",
        f"- run_standard_b4_sweeps_now: `{decision['run_standard_b4_sweeps_now']}`",
        f"- run_last_token_mb512_validation_now: `{decision['run_last_token_mb512_validation_now']}`",
        f"- run_capacity_partition_probe_now: `{decision['run_capacity_partition_probe_now']}`",
        f"- reason: `{decision['reason']}`",
        "",
        "## Standard B=4 Coverage",
        "",
        f"- NAS B=4 group-major reports: `{standard['nas_b4_group_major_report_count']}`",
        f"- local B=4 telemetry JSON files: `{standard['local_b4_json_count']}`",
        f"- successful / failed: `{standard['successful_b4_runs']} / {standard['failed_capacity_probes']}`",
        f"- by_microbatch_count: `{standard['by_microbatch_count']}`",
        f"- by_group_count: `{standard['by_group_count']}`",
        f"- run_more_standard_b4_runtime_sweeps_now: `{standard['run_more_standard_b4_runtime_sweeps_now']}`",
        "",
        "## Service Gate",
        "",
        f"- ready: `{service['ready']}`",
        f"- freshness_verdict: `{service['freshness_verdict']}`",
        f"- freshness_failed_checks: `{service['freshness_failed_checks']}`",
        f"- slo_verdict: `{service['slo_verdict']}`",
        f"- slo_freshness_required: `{service['slo_freshness_required']}`",
        f"- slo_freshness_accepted: `{service['slo_freshness_accepted']}`",
        "",
        "## Admission Evidence",
        "",
        f"- ready: `{admission['ready']}`",
        f"- final_logits_leverage_gate_ready: `{admission['final_logits_leverage_gate_ready']}`",
        f"- runtime_refactor_gate_ready: `{admission['runtime_refactor_gate_ready']}`",
        f"- tuning_matrix_gate_ready: `{admission['tuning_matrix_gate_ready']}`",
        f"- projected_saved_ms_per_request: `{admission['projected_saved_ms_per_request']}`",
        f"- projection_is_not_bpu_promotion_proof: `{admission['projection_is_not_bpu_promotion_proof']}`",
        f"- do_not_promote_without_runtime_result: `{admission['do_not_promote_without_runtime_result']}`",
        f"- standard_group_or_inner_order_sweeps_blocked: `{admission['standard_group_or_inner_order_sweeps_blocked']}`",
        f"- runtime_refactor_primary_target: `{admission['runtime_refactor_primary_target']}`",
        f"- tuning_primary_code_target: `{admission['tuning_primary_code_target']}`",
        f"- per_run_matrix_gate_ready: `{admission['per_run_matrix_gate_ready']}`",
        f"- per_run_matrix_top_segment: `{admission['per_run_matrix_top_segment']}`",
        f"- per_run_matrix_top_segment_rate: `{admission['per_run_matrix_top_segment_rate']}`",
        f"- per_run_matrix_standard_sweep_status: `{admission['per_run_matrix_standard_sweep_status']}`",
        f"- per_run_matrix_next_nonduplicate_runtime_candidate: `{admission['per_run_matrix_next_nonduplicate_runtime_candidate']}`",
        "",
        "## Per-Run Evidence Matrix",
        "",
        f"- verdict: `{per_run['verdict']}`",
        f"- gate_ready: `{per_run['gate_ready']}`",
        f"- run_count: `{per_run['run_count']}`",
        f"- successful_run_count: `{per_run['successful_run_count']}`",
        f"- failed_run_count: `{per_run['failed_run_count']}`",
        f"- would_start_runtime: `{per_run['would_start_runtime']}`",
        f"- would_start_compile: `{per_run['would_start_compile']}`",
        "",
        "## Last-Token Candidate",
        "",
        f"- compile_ready: `{last_token['compile_ready']}`",
        f"- manifest_ready: `{last_token['manifest_ready']}`",
        f"- runtime_validation_ready: `{last_token['runtime_validation_ready']}`",
        f"- experiment_ready: `{last_token['experiment_ready']}`",
        f"- candidate_result_exists: `{last_token['candidate_result_exists']}`",
        f"- validation_compare_verdict: `{last_token['validation_compare_verdict']}`",
        f"- compile_blockers: `{last_token['compile_blockers']}`",
        f"- experiment_gate_blockers: `{last_token['experiment_gate_blockers']}`",
        f"- runtime_validation_blockers: `{last_token['runtime_validation_blockers']}`",
        "",
        "## Partition Candidate",
        "",
        f"- planner_verdict: `{partition['planner_verdict']}`",
        f"- candidate_count: `{partition['candidate_count']}`",
        f"- run_new_partition_now: `{partition['run_new_partition_now']}`",
        f"- only_probe_if_memory_plan_changes: `{partition['only_probe_if_memory_plan_changes']}`",
        f"- reason: `{partition['reason']}`",
        "",
        "## Post-Instrumentation Segment Attribution",
        "",
        f"- verdict: `{post_segment['verdict']}`",
        f"- primary_single_segment_bottleneck: `{post_segment['primary_single_segment_bottleneck']}`",
        f"- final_logits_compute_still_primary: `{post_segment['final_logits_compute_still_primary']}`",
        f"- top_group_by_segment_total: `{post_segment['top_group_by_segment_total']}`",
        f"- top_group_contains_final_logits: `{post_segment['top_group_contains_final_logits']}`",
        f"- group_size_tuning_implication: `{post_segment['group_size_tuning_implication']}`",
        f"- inner_order_tuning_implication: `{post_segment['inner_order_tuning_implication']}`",
        f"- blocks_standard_group_sweeps: `{post_segment['blocks_standard_group_sweeps']}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- `{item}`" for item in payload["blockers"])
    lines.extend(
        [
            "",
            "## Duplicate Stop Rules",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["duplicate_stop_rules"])
    lines.extend(
        [
            "",
            "## Remaining Non-Duplicate Work",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["remaining_nonduplicate_work"])
    lines.extend(
        [
            "",
            "## Source Paths",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in payload["source_paths"].items())
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate whether a new Dream7B B=4 S100P runtime experiment should run.")
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument("--snapshot-root", type=Path, default=DEFAULT_SNAPSHOT_ROOT)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()
    payload = build_payload(args)
    write_report(payload, args.out_json, args.out_md)
    print(args.out_json)
    print(args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
