#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_b4_group_inner_order_value_audit"
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


def observed_variant_rows(group_order: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in group_order.get("observed_variants") or []:
        rows.append(
            {
                "label": row.get("label"),
                "inner_order": row.get("inner_order"),
                "group_count": row.get("group_count"),
                "group_ranges": row.get("group_ranges") or [],
                "ms_per_request": row.get("ms_per_request"),
                "delta_ms_per_request_vs_baseline": row.get(
                    "delta_ms_per_request_vs_baseline"
                ),
                "delta_avg_bpu_vs_baseline": row.get("delta_avg_bpu_vs_baseline"),
                "delta_nonzero_bpu_vs_baseline": row.get(
                    "delta_nonzero_bpu_vs_baseline"
                ),
                "beats_baseline": (
                    as_float(row.get("delta_ms_per_request_vs_baseline")) is not None
                    and float(row.get("delta_ms_per_request_vs_baseline")) < 0
                ),
                "source_file": row.get("file"),
            }
        )
    return rows


def candidate_rows(partition: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    rows = []
    for row in (partition.get("top_capacity_probe_candidates") or [])[:limit]:
        rows.append(
            {
                "group_ranges": row.get("group_ranges") or [],
                "group_count": row.get("group_count"),
                "max_group_hbm_mib": row.get("max_group_hbm_mib"),
                "peak_hbm_delta_pct_vs_baseline": row.get(
                    "peak_hbm_delta_pct_vs_baseline"
                ),
                "final_logits_singleton_group": row.get("final_logits_singleton_group"),
                "estimated_release_delta_ms_per_request": row.get(
                    "estimated_release_delta_ms_per_request"
                ),
                "recommendation": row.get("recommendation"),
            }
        )
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    root = args.analysis_root
    paths = {
        "group_order": root / "dream7b_b4_group_order_candidate_analysis_20260620.json",
        "group_partition": root / "dream7b_b4_group_partition_planner_20260620.json",
        "segment_stability": root / "dream7b_b4_segment_stability_audit_20260620.json",
        "segment_bottleneck": root / "dream7b_b4_segment_bottleneck_scorecard_20260620.json",
        "tuning_decision_matrix": root / "dream7b_b4_tuning_decision_matrix_20260621.json",
        "final_logits_leverage": root / "dream7b_b4_final_logits_leverage_model_20260621.json",
    }
    group_order = read_json(paths["group_order"])
    partition = read_json(paths["group_partition"])
    stability = read_json(paths["segment_stability"])
    bottleneck = read_json(paths["segment_bottleneck"])
    tuning = read_json(paths["tuning_decision_matrix"])
    leverage = read_json(paths["final_logits_leverage"])

    order_decision = group_order.get("decision") or {}
    partition_decision = partition.get("decision") or {}
    stability_summary = stability.get("summary") or {}
    stability_decision = stability.get("decision") or {}
    bottleneck_decision = bottleneck.get("decision") or {}
    tuning_decision = tuning.get("decision") or {}
    leverage_decision = leverage.get("decision") or {}

    variants = observed_variant_rows(group_order)
    nonbaseline = [
        row
        for row in variants
        if row.get("label") != order_decision.get("baseline")
        and row.get("delta_ms_per_request_vs_baseline") is not None
    ]
    best_nonbaseline = min(
        nonbaseline,
        key=lambda row: as_float(row.get("delta_ms_per_request_vs_baseline"))
        if as_float(row.get("delta_ms_per_request_vs_baseline")) is not None
        else float("inf"),
        default={},
    )
    slower_or_equal_nonbaseline_count = sum(
        1
        for row in nonbaseline
        if as_float(row.get("delta_ms_per_request_vs_baseline")) is not None
        and float(row.get("delta_ms_per_request_vs_baseline")) >= 0
    )
    capacity_candidates = candidate_rows(partition, args.capacity_candidate_limit)
    recommendation_counts = partition.get("recommendation_counts") or {}
    final_to_token = as_float(stability_summary.get("final_to_token_excess_ratio"))
    final_to_hidden = as_float(stability_summary.get("final_to_max_hidden_excess_ratio"))
    projection_saved = as_float(
        tuning_decision.get("primary_code_target_projected_saved_ms_per_request")
    )
    best_variant_delta = as_float(best_nonbaseline.get("delta_ms_per_request_vs_baseline"))

    checks = {
        "observed_nonbaseline_variants_do_not_beat_baseline": (
            bool(nonbaseline) and slower_or_equal_nonbaseline_count == len(nonbaseline)
        ),
        "segment_major_preferred": order_decision.get(
            "segment_major_preferred_over_microbatch_major"
        )
        is True
        and bottleneck_decision.get("preferred_inner_order") == "segment-major",
        "partition_search_complete": partition_decision.get(
            "systematic_partition_search_complete"
        )
        is True,
        "new_partition_runtime_blocked_now": partition_decision.get(
            "run_new_partition_now"
        )
        is False,
        "capacity_probe_candidates_are_memory_only": all(
            row.get("recommendation") == "capacity_probe_only_if_memory_plan_changes"
            for row in capacity_candidates
        ),
        "final_logits_stable_primary": stability_decision.get(
            "final_logits_stable_rank1"
        )
        is True
        and stability_decision.get("stable_primary_bottleneck")
        == "seg27_28_final_logits",
        "hidden_inner_order_not_primary": stability_decision.get(
            "hidden_inner_order_tuning_not_primary"
        )
        is True,
        "standard_sweeps_blocked_by_final_logits": leverage_decision.get(
            "do_not_run_standard_group_or_inner_order_sweeps"
        )
        is True
        and tuning_decision.get(
            "standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage"
        )
        is True,
        "next_runtime_experiment_allowed_now": tuning_decision.get(
            "next_s100p_runtime_experiment_allowed"
        )
        is False,
        "next_compile_allowed_now": tuning_decision.get("next_compile_allowed") is False,
    }
    failed_checks = [key for key, value in checks.items() if not value]
    value_rankings = [
        {
            "rank": 1,
            "lever": "seg27_28_last_token_logits_or_output_avoidance",
            "current_status": "primary_candidate_after_manifest_compile_gate",
            "expected_value": "highest_latency_value_but_not_bpu_promotion_proof",
            "evidence": {
                "projected_saved_ms_per_request": round_or_none(projection_saved),
                "final_to_token_excess_ratio": round_or_none(final_to_token, 3),
                "final_to_max_hidden_excess_ratio": round_or_none(final_to_hidden, 3),
            },
        },
        {
            "rank": 2,
            "lever": "capacity_probe_partition_if_memory_plan_changes",
            "current_status": "defer_until_last_token_or_residency_memory_plan_changes",
            "expected_value": "memory_headroom_only_no_runtime_win_observed",
            "evidence": {
                "top_candidate_group_ranges": (
                    capacity_candidates[0].get("group_ranges") if capacity_candidates else []
                ),
                "top_candidate_peak_hbm_delta_pct_vs_baseline": (
                    capacity_candidates[0].get("peak_hbm_delta_pct_vs_baseline")
                    if capacity_candidates
                    else None
                ),
                "recommendation_count": recommendation_counts.get(
                    "capacity_probe_only_if_memory_plan_changes"
                ),
            },
        },
        {
            "rank": 3,
            "lever": "more_mb512_group_boundary_or_inner_order_sweeps",
            "current_status": "blocked_as_duplicate_low_value",
            "expected_value": "negative_or_noise_band_based_on_existing_runs",
            "evidence": {
                "best_nonbaseline_variant": best_nonbaseline.get("label"),
                "best_nonbaseline_delta_ms_per_request": round_or_none(best_variant_delta),
                "observed_nonbaseline_count": len(nonbaseline),
                "slower_or_equal_nonbaseline_count": slower_or_equal_nonbaseline_count,
            },
        },
        {
            "rank": 4,
            "lever": "hidden_block_inner_order_tuning",
            "current_status": "blocked_until_hidden_materialize_plan_changes",
            "expected_value": "too_small_relative_to_final_logits",
            "evidence": {
                "max_hidden_mean_positive_excess_ms_per_request": stability_summary.get(
                    "max_hidden_mean_positive_excess_ms_per_request"
                ),
                "final_to_max_hidden_excess_ratio": round_or_none(final_to_hidden, 3),
            },
        },
    ]
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": (
            "ok_dream7b_b4_group_inner_order_value_audit"
            if not failed_checks
            else "warning_dream7b_b4_group_inner_order_value_audit"
        ),
        "source_paths": {key: str(path) for key, path in paths.items()},
        "summary": {
            "baseline": order_decision.get("baseline"),
            "preferred_inner_order": bottleneck_decision.get("preferred_inner_order"),
            "preferred_group_policy": bottleneck_decision.get("preferred_group_policy"),
            "observed_variant_count": len(variants),
            "observed_nonbaseline_count": len(nonbaseline),
            "best_nonbaseline_variant": best_nonbaseline.get("label"),
            "best_nonbaseline_delta_ms_per_request": round_or_none(best_variant_delta),
            "slower_or_equal_nonbaseline_count": slower_or_equal_nonbaseline_count,
            "capacity_probe_only_candidate_count": recommendation_counts.get(
                "capacity_probe_only_if_memory_plan_changes"
            ),
            "do_not_repeat_observed_non_better_variant_count": recommendation_counts.get(
                "do_not_repeat_observed_non_better_variant"
            ),
            "final_logits_rank1_rate": stability_summary.get("final_logits_rank1_rate"),
            "final_logits_mean_positive_excess_ms_per_request": stability_summary.get(
                "final_logits_mean_positive_excess_ms_per_request"
            ),
            "final_to_token_excess_ratio": round_or_none(final_to_token, 3),
            "final_to_max_hidden_excess_ratio": round_or_none(final_to_hidden, 3),
            "primary_code_target_projected_saved_ms_per_request": round_or_none(
                projection_saved
            ),
        },
        "observed_variants": variants,
        "capacity_probe_candidates": capacity_candidates,
        "value_rankings": value_rankings,
        "checks": checks,
        "failed_checks": failed_checks,
        "decision": {
            "run_more_group_size_or_inner_order_sweeps_now": False,
            "group_size_and_inner_order_are_current_primary_levers": False,
            "keep_current_group_policy": bottleneck_decision.get("preferred_group_policy"),
            "keep_current_inner_order": bottleneck_decision.get("preferred_inner_order"),
            "only_capacity_probe_if_memory_plan_changes": partition_decision.get(
                "only_probe_if_memory_plan_changes"
            ),
            "primary_runtime_candidate_before_new_group_sweeps": tuning_decision.get(
                "primary_code_target"
            ),
            "next_s100p_runtime_experiment_allowed_now": False,
            "next_compile_allowed_now": False,
            "recommended_next": (
                "keep 5-group segment-major as the B=4 true-batch analysis baseline; "
                "use lower-HBM partitions only after the last-token/residency memory plan changes"
            ),
        },
        "audit": {
            "runtime_started": False,
            "compile_started": False,
            "remote_write_performed": False,
            "service_restarted": False,
            "local_writes": "JSON/Markdown group-inner-order value audit only",
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B=4 Group/Inner-Order Value Audit",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- failed_checks: `{payload['failed_checks']}`",
        f"- run_more_group_size_or_inner_order_sweeps_now: `{decision['run_more_group_size_or_inner_order_sweeps_now']}`",
        f"- keep_current_group_policy: `{decision['keep_current_group_policy']}`",
        f"- keep_current_inner_order: `{decision['keep_current_inner_order']}`",
        f"- primary_runtime_candidate_before_new_group_sweeps: `{decision['primary_runtime_candidate_before_new_group_sweeps']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Value Rankings", ""])
    for item in payload["value_rankings"]:
        lines.append(
            f"- {item['rank']}. `{item['lever']}`: `{item['current_status']}`; "
            f"expected_value `{item['expected_value']}`; evidence `{item['evidence']}`"
        )
    lines.extend(["", "## Observed Variants", ""])
    lines.append("| label | order | groups | ms/request | delta vs baseline | beats baseline |")
    lines.append("| --- | --- | ---: | ---: | ---: | --- |")
    for row in payload["observed_variants"]:
        lines.append(
            f"| {row['label']} | {row['inner_order']} | {row['group_count']} | "
            f"{row['ms_per_request']} | {row['delta_ms_per_request_vs_baseline']} | "
            f"{row['beats_baseline']} |"
        )
    lines.extend(["", "## Capacity Probe Candidates", ""])
    lines.append("| ranges | groups | max_hbm_mib | hbm_delta_pct | release_delta_ms/request |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for row in payload["capacity_probe_candidates"]:
        lines.append(
            f"| {row['group_ranges']} | {row['group_count']} | {row['max_group_hbm_mib']} | "
            f"{row['peak_hbm_delta_pct_vs_baseline']} | "
            f"{row['estimated_release_delta_ms_per_request']} |"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["checks"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rank remaining Dream7B B=4 group-size and inner-order tuning value from existing telemetry only."
    )
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument("--capacity-candidate-limit", type=int, default=5)
    parser.add_argument(
        "--out-json",
        type=Path,
        default=DEFAULT_ANALYSIS_ROOT / "dream7b_b4_group_inner_order_value_audit_20260621.json",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=DEFAULT_ANALYSIS_ROOT / "dream7b_b4_group_inner_order_value_audit_20260621.md",
    )
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_markdown(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
