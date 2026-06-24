#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_b4_segment_group_schedule_scorecard"
DEFAULT_ANALYSIS_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    return round(number, digits) if number is not None else None


def ratio_or_none(numerator: Any, denominator: Any, digits: int = 3) -> float | None:
    num = as_float(numerator)
    den = as_float(denominator)
    if num is None or den in (None, 0.0):
        return None
    return round(num / den, digits)


def compact_segment(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": row.get("index"),
        "kind": row.get("kind"),
        "group": row.get("group"),
        "avg_run_ms": row.get("avg_run_ms"),
        "run_ms_per_request": row.get("run_ms_per_request"),
        "compute_excess_ms_per_request": row.get(
            "compute_excess_vs_hidden_ms_per_request"
        ),
        "segment_total_ms_per_request": row.get("segment_total_ms_per_request"),
        "output_postprocess_ms_per_request": row.get("output_postprocess_ms_per_request"),
        "hidden_materialize_ms_per_request": row.get("hidden_materialize_ms_per_request"),
        "load_ms_per_request": row.get("load_ms_per_request"),
        "completed_microbatch_count": row.get("completed_microbatch_count"),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    root = args.analysis_root
    paths = {
        "segment_drag": root / "dream7b_b4_segment_drag_breakdown_20260619.json",
        "post_segment": root / "dream7b_b4_post_instrumentation_segment_attribution_20260621.json",
        "group_inner_order_value": root
        / "dream7b_b4_group_inner_order_value_audit_20260621.json",
        "group_switch": root / "dream7b_b4_group_switch_accounting_20260619.json",
        "tuning_matrix": root / "dream7b_b4_tuning_decision_matrix_20260621.json",
        "bottleneck_closure": root / "dream7b_b4_bottleneck_closure_model_20260621.json",
        "runtime_refactor_admission": root
        / "dream7b_b4_runtime_refactor_admission_contract_20260621.json",
    }
    segment_drag = read_json(paths["segment_drag"])
    post_segment = read_json(paths["post_segment"])
    group_value = read_json(paths["group_inner_order_value"])
    group_switch = read_json(paths["group_switch"])
    tuning = read_json(paths["tuning_matrix"])
    closure = read_json(paths["bottleneck_closure"])
    admission = read_json(paths["runtime_refactor_admission"])

    post_decision = post_segment.get("decision") or {}
    totals = post_segment.get("totals") or {}
    key_segments = post_segment.get("key_segments") or {}
    group_summary = group_value.get("summary") or {}
    group_decision = group_value.get("decision") or {}
    switch_decision = group_switch.get("decision") or {}
    latest_switch = group_switch.get("latest_default_summary") or {}
    tuning_decision = tuning.get("decision") or {}
    closure_decision = closure.get("decision") or {}
    closure_components = closure.get("components_ms_per_request") or {}
    admission_summary = admission.get("summary") or {}
    admission_decision = admission.get("decision") or {}
    latest_focus = segment_drag.get("latest_default_focus") or {}

    final_logits = key_segments.get("final_logits") or {}
    token = key_segments.get("token_embedding") or {}
    top_hidden = key_segments.get("top_hidden_by_compute_excess") or {}
    final_compute_excess = totals.get("final_compute_excess_ms_per_request")
    group_switch_gap = latest_switch.get(
        "group_switch_gap_ms_per_request",
        closure_components.get("group_switch_gap"),
    )
    best_group_delta = group_summary.get("best_nonbaseline_delta_ms_per_request")

    scorecard_rows = [
        {
            "rank": 1,
            "target": "seg27_28_last_token_logits_or_output_avoidance",
            "class": "active_compute_or_output",
            "status": "primary_next_candidate_but_runtime_blocked",
            "allowed_now": False,
            "estimated_saved_ms_per_request": tuning_decision.get(
                "primary_code_target_projected_saved_ms_per_request"
            ),
            "why": "final logits is the stable segment-level outlier; projection is latency-only and still needs a real last-token run.",
            "evidence": {
                "primary_single_segment_bottleneck": post_decision.get(
                    "primary_single_segment_bottleneck"
                ),
                "final_segment_total_ms_per_request": final_logits.get(
                    "segment_total_ms_per_request"
                ),
                "final_compute_excess_ms_per_request": final_compute_excess,
                "final_to_top_hidden_compute_excess_ratio": totals.get(
                    "final_to_top_hidden_compute_excess_ratio"
                ),
                "compile_start_allowed_now": admission_summary.get(
                    "compile_start_allowed_now"
                ),
                "s100p_runtime_experiment_allowed_now": admission_summary.get(
                    "s100p_runtime_experiment_allowed_now"
                ),
            },
        },
        {
            "rank": 2,
            "target": "keep_existing_5_group_segment_major_default",
            "class": "group_policy",
            "status": "keep_current_baseline",
            "allowed_now": True,
            "estimated_saved_ms_per_request": 0.0,
            "why": "all observed mb512 group-count and inner-order variants are slower or equal to the 5-group segment-major baseline.",
            "evidence": {
                "preferred_group_policy": tuning_decision.get("preferred_group_policy"),
                "preferred_inner_order": tuning_decision.get("preferred_inner_order"),
                "observed_nonbaseline_count": group_summary.get(
                    "observed_nonbaseline_count"
                ),
                "slower_or_equal_nonbaseline_count": group_summary.get(
                    "slower_or_equal_nonbaseline_count"
                ),
                "best_nonbaseline_delta_ms_per_request": best_group_delta,
            },
        },
        {
            "rank": 3,
            "target": "lower_peak_hbm_partition",
            "class": "capacity_probe_only",
            "status": "defer_until_memory_residency_plan_changes",
            "allowed_now": False,
            "estimated_saved_ms_per_request": None,
            "why": "partition search found lower peak-HBM candidates, but existing runtime variants did not improve wall time.",
            "evidence": {
                "top_capacity_probe_group_ranges": group_decision.get(
                    "only_capacity_probe_if_memory_plan_changes"
                ),
                "capacity_probe_candidate_count": group_summary.get(
                    "capacity_probe_only_candidate_count"
                ),
                "run_more_group_size_or_inner_order_sweeps_now": group_decision.get(
                    "run_more_group_size_or_inner_order_sweeps_now"
                ),
            },
        },
        {
            "rank": 4,
            "target": "python_inter_segment_or_group_switch_gap",
            "class": "scheduler_gap",
            "status": "deprioritized",
            "allowed_now": False,
            "estimated_saved_ms_per_request": group_switch_gap,
            "why": "measured group switch/release gap is far smaller than the final-logits compute excess.",
            "evidence": {
                "group_switch_gap_ms_per_request": group_switch_gap,
                "final_excess_to_group_switch_gap_ratio": ratio_or_none(
                    final_compute_excess, group_switch_gap
                ),
                "group_release_and_unaccounted_gap_not_primary": switch_decision.get(
                    "group_release_and_unaccounted_gap_not_primary"
                ),
            },
        },
        {
            "rank": 5,
            "target": "hidden_materialize_alternative_design",
            "class": "local_design_only",
            "status": "design_only_allowed_current_preallocate_path_rejected",
            "allowed_now": bool(
                admission_summary.get("design_only_hidden_materialize_allowed_now")
            ),
            "estimated_saved_ms_per_request": closure_components.get(
                "hidden_materialize"
            ),
            "why": "hidden materialize has a bounded ceiling, but the measured preallocate-hidden implementation was slower.",
            "evidence": {
                "hidden_materialize_ms_per_request": totals.get(
                    "hidden_materialize_ms_per_request"
                ),
                "secondary_research_target": post_decision.get(
                    "secondary_research_target"
                ),
                "default_runtime_code_change_allowed_now": admission_summary.get(
                    "default_runtime_code_change_allowed_now"
                ),
            },
        },
        {
            "rank": 6,
            "target": "token_embedding_residency",
            "class": "followup_after_final_logits",
            "status": "not_primary_now",
            "allowed_now": False,
            "estimated_saved_ms_per_request": token.get(
                "compute_excess_vs_hidden_ms_per_request"
            ),
            "why": "token embedding carries load, but active compute excess is small compared with final logits.",
            "evidence": {
                "token_compute_excess_ms_per_request": token.get(
                    "compute_excess_vs_hidden_ms_per_request"
                ),
                "token_load_ms_per_request": token.get("load_ms_per_request"),
                "token_to_final_compute_excess_ratio": ratio_or_none(
                    token.get("compute_excess_vs_hidden_ms_per_request"),
                    final_compute_excess,
                    digits=4,
                ),
            },
        },
    ]

    checks = {
        "post_segment_final_logits_primary": post_decision.get(
            "primary_single_segment_bottleneck"
        )
        == "seg27_28_final_logits"
        and post_decision.get("final_logits_compute_still_primary") is True,
        "group_policy_keeps_5_group_segment_major": tuning_decision.get(
            "preferred_group_policy"
        )
        == "keep_existing_5_group_segment_major_default"
        and tuning_decision.get("preferred_inner_order") == "segment-major",
        "group_inner_order_sweeps_blocked": group_decision.get(
            "run_more_group_size_or_inner_order_sweeps_now"
        )
        is False
        and group_decision.get("next_s100p_runtime_experiment_allowed_now") is False,
        "group_switch_not_primary": switch_decision.get(
            "group_release_and_unaccounted_gap_not_primary"
        )
        is True,
        "admission_blocks_runtime_compile_defaults": admission_summary.get(
            "queue_batch_remains_default"
        )
        is True
        and admission_summary.get("default_runtime_code_change_allowed_now") is False
        and admission_summary.get("s100p_runtime_experiment_allowed_now") is False
        and admission_summary.get("compile_start_allowed_now") is False
        and admission_summary.get("compile_preflight_only_allowed_now") is True,
        "queue_batch_remains_default": closure_decision.get(
            "queue_batch_remains_production_default"
        )
        is True,
    }
    failed_checks = [key for key, value in checks.items() if not value]

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": (
            f"ok_{TOOL_ID}" if not failed_checks else f"warning_{TOOL_ID}"
        ),
        "source_paths": {key: str(path) for key, path in paths.items()},
        "summary": {
            "latest_default_microbatch_count": latest_focus.get("microbatch_count"),
            "latest_default_ms_per_request": latest_focus.get("ms_per_request"),
            "latest_default_avg_bpu_loading": latest_focus.get("avg_bpu_loading"),
            "latest_default_avg_nonzero_bpu_loading": latest_focus.get(
                "avg_nonzero_bpu_loading"
            ),
            "primary_single_segment_bottleneck": post_decision.get(
                "primary_single_segment_bottleneck"
            ),
            "final_logits_segment_total_ms_per_request": final_logits.get(
                "segment_total_ms_per_request"
            ),
            "final_logits_compute_excess_ms_per_request": final_compute_excess,
            "final_logits_output_postprocess_ms_per_request": totals.get(
                "final_output_postprocess_ms_per_request"
            ),
            "top_hidden_compute_excess_ms_per_request": top_hidden.get(
                "compute_excess_vs_hidden_ms_per_request"
            ),
            "token_compute_excess_ms_per_request": token.get(
                "compute_excess_vs_hidden_ms_per_request"
            ),
            "final_to_top_hidden_compute_excess_ratio": totals.get(
                "final_to_top_hidden_compute_excess_ratio"
            ),
            "group_switch_gap_ms_per_request": group_switch_gap,
            "final_excess_to_group_switch_gap_ratio": ratio_or_none(
                final_compute_excess, group_switch_gap
            ),
            "best_nonbaseline_group_delta_ms_per_request": best_group_delta,
            "observed_nonbaseline_group_or_order_count": group_summary.get(
                "observed_nonbaseline_count"
            ),
            "capacity_probe_only_candidate_count": group_summary.get(
                "capacity_probe_only_candidate_count"
            ),
            "primary_code_target_projected_saved_ms_per_request": tuning_decision.get(
                "primary_code_target_projected_saved_ms_per_request"
            ),
        },
        "key_segments": {
            "final_logits": compact_segment(final_logits),
            "token_embedding": compact_segment(token),
            "top_hidden_by_compute_excess": compact_segment(top_hidden),
        },
        "scorecard_rows": scorecard_rows,
        "decision": {
            "production_default": "queue_batch",
            "true_batch_b4_status": "research_artifact_not_promoted",
            "primary_schedule_bottleneck": "seg27_28_final_logits",
            "primary_code_target": tuning_decision.get("primary_code_target"),
            "preferred_group_policy": tuning_decision.get("preferred_group_policy"),
            "preferred_inner_order": tuning_decision.get("preferred_inner_order"),
            "run_more_standard_b4_group_or_inner_order_sweeps_now": False,
            "run_new_group_partition_now": False,
            "run_s100p_runtime_now": admission_decision.get("admit_s100p_runtime_now"),
            "start_compile_now": admission_decision.get("admit_compile_start_now"),
            "compile_preflight_only_now": admission_decision.get(
                "admit_compile_preflight_only_now"
            ),
            "local_report_only_refactor_allowed_now": admission_decision.get(
                "admit_local_report_only_refactor_now"
            ),
            "next_runtime_candidate_after_readiness": admission_summary.get(
                "only_future_runtime_candidate"
            ),
            "recommended_next": (
                "keep queue-batch default and 5-group segment-major B=4 analysis "
                "baseline; only move to seg27_28 last-token validation after "
                "compile/manifest readiness passes"
            ),
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "audit": {
            "runtime_started": False,
            "compile_started": False,
            "remote_access_performed": False,
            "service_restarted": False,
            "local_writes": "JSON/Markdown segment-group schedule scorecard only",
        },
    }


def render_md(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Dream7B B=4 Segment/Group Schedule Scorecard",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Decision",
            "",
        ]
    )
    for key, value in payload["decision"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Scorecard Rows",
            "",
            "| rank | target | class | status | allowed_now | estimated_saved_ms_per_request | why |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["scorecard_rows"]:
        lines.append(
            "| {rank} | {target} | {klass} | {status} | {allowed} | {saved} | {why} |".format(
                rank=row.get("rank"),
                target=row.get("target"),
                klass=row.get("class"),
                status=row.get("status"),
                allowed=row.get("allowed_now"),
                saved=row.get("estimated_saved_ms_per_request"),
                why=row.get("why"),
            )
        )
    lines.extend(
        [
            "",
            "## Key Segments",
            "",
        ]
    )
    for name, row in payload["key_segments"].items():
        lines.append(f"### {name}")
        for key, value in row.items():
            lines.append(f"- {key}: `{value}`")
        lines.append("")
    lines.extend(
        [
            "## Checks",
            "",
        ]
    )
    for key, value in payload["checks"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append(f"- failed_checks: `{payload['failed_checks']}`")
    lines.extend(
        [
            "",
            "## Audit",
            "",
        ]
    )
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Source Paths",
            "",
        ]
    )
    for key, value in payload["source_paths"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument(
        "--out-json",
        type=Path,
        default=DEFAULT_ANALYSIS_ROOT
        / "dream7b_b4_segment_group_schedule_scorecard_20260621.json",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=DEFAULT_ANALYSIS_ROOT
        / "dream7b_b4_segment_group_schedule_scorecard_20260621.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    render_md(payload, args.out_md)
    print(args.out_json)
    print(args.out_md)
    return 0 if not payload["failed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
