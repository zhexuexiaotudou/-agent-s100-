#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_bottleneck_closure_model_20260621.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_bottleneck_closure_model_20260621.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def projected_avg_bpu_if_wall_only_saved(
    avg_bpu: float,
    ms_per_request: float,
    saved_ms_per_request: float,
) -> float | None:
    projected_ms = ms_per_request - saved_ms_per_request
    if avg_bpu <= 0 or ms_per_request <= 0 or projected_ms <= 0:
        return None
    return min(100.0, avg_bpu * ms_per_request / projected_ms)


def candidate(
    name: str,
    category: str,
    saved_ms: float,
    latest_ms: float,
    latest_avg_bpu: float,
    queue_avg_bpu: float,
    changes_active_compute: bool,
    evidence: str,
    decision: str,
) -> dict[str, Any]:
    projected_ms = latest_ms - saved_ms
    projected_avg = projected_avg_bpu_if_wall_only_saved(
        latest_avg_bpu,
        latest_ms,
        saved_ms,
    )
    return {
        "name": name,
        "category": category,
        "estimated_saved_ms_per_request": round_or_none(saved_ms),
        "projected_ms_per_request": round_or_none(projected_ms),
        "latency_reduction_pct": round_or_none(
            saved_ms / latest_ms * 100 if latest_ms else None,
            3,
        ),
        "wall_only_projected_avg_bpu": round_or_none(projected_avg, 3),
        "wall_only_avg_bpu_gap_to_queue_points": round_or_none(
            projected_avg - queue_avg_bpu
            if projected_avg is not None
            else None,
            3,
        ),
        "changes_active_compute": changes_active_compute,
        "bpu_promotion_proof": False,
        "evidence": evidence,
        "decision": decision,
    }


def build_payload(root: Path) -> dict[str, Any]:
    schedule_path = root / "dream7b_true_batch_b4_schedule_analysis_current.json"
    group_switch_path = root / "dream7b_b4_group_switch_accounting_20260619.json"
    final_logits_path = root / "dream7b_b4_final_logits_leverage_model_20260621.json"
    post_overhead_path = root / "dream7b_b4_post_instrumentation_overhead_analysis_20260621.json"
    hbm_load_path = root / "dream7b_b4_hbm_load_breakdown_20260619.json"
    group_inner_path = root / "dream7b_b4_group_inner_order_value_audit_20260621.json"

    schedule = read_json(schedule_path)
    group_switch = read_json(group_switch_path)
    final_logits = read_json(final_logits_path)
    post_overhead = read_json(post_overhead_path)
    hbm_load = read_json(hbm_load_path)
    group_inner = read_json(group_inner_path)

    queue = schedule.get("queue_baseline") or {}
    latest = group_switch.get("latest_default_summary") or {}
    final_leverage = final_logits.get("leverage") or {}
    bpu_gap = final_logits.get("bpu_promotion_gap") or {}
    overhead = post_overhead.get("totals") or {}
    hbm_decision = hbm_load.get("decision") or {}
    group_inner_decision = group_inner.get("decision") or {}

    latest_ms = as_float(latest.get("ms_per_request"))
    latest_avg = as_float(latest.get("avg_bpu_loading"))
    latest_nonzero = as_float(latest.get("avg_nonzero_bpu_loading"))
    queue_ms = as_float(queue.get("amortized_wall_ms_per_processed_request"))
    queue_avg = as_float(queue.get("avg_bpu_loading"))
    queue_nonzero = as_float(queue.get("avg_nonzero_bpu_loading"))

    group_switch_gap = as_float(latest.get("group_switch_gap_ms_per_request"))
    release_gap = as_float(latest.get("group_release_ms_per_request")) + as_float(
        latest.get("unaccounted_gap_ms_per_request")
    )
    hidden_materialize = as_float(latest.get("hidden_materialize_ms_per_request"))
    nonhidden_python = as_float(
        latest.get("segment_overhead_excluding_hidden_materialize_ms_per_request")
    )
    hbm_group_load = as_float(latest.get("group_load_ms_per_request"))
    final_projection = as_float(final_leverage.get("projection_saved_ms_per_request"))
    final_excess = as_float(final_leverage.get("final_excess_ms_per_request_if_hidden_speed"))
    output_postprocess = as_float(overhead.get("output_postprocess_ms_per_request"))
    input_prepare = as_float(overhead.get("input_prepare_ms_per_request"))
    final_output_postprocess = as_float(
        overhead.get("final_output_postprocess_ms_per_request")
    )

    candidates = [
        candidate(
            "release_plus_unaccounted_group_gap",
            "scheduler_gap",
            release_gap,
            latest_ms,
            latest_avg,
            queue_avg,
            False,
            "latest group-switch accounting release + unaccounted gap",
            "do_not_prioritize",
        ),
        candidate(
            "nonhidden_python_segment_overhead",
            "python_overhead",
            nonhidden_python,
            latest_ms,
            latest_avg,
            queue_avg,
            False,
            "latest segment overhead excluding hidden materialize",
            "secondary_only_after_final_logits",
        ),
        candidate(
            "hidden_materialize_theoretical_zero",
            "materialization",
            hidden_materialize,
            latest_ms,
            latest_avg,
            queue_avg,
            False,
            "latest hidden materialize accounting; current preallocate-hidden A/B was slower",
            "do_not_default_current_preallocate_hidden",
        ),
        candidate(
            "input_prepare_theoretical_zero",
            "python_overhead",
            input_prepare,
            latest_ms,
            latest_avg,
            queue_avg,
            False,
            "post-instrumentation overhead analysis",
            "not_primary",
        ),
        candidate(
            "output_postprocess_theoretical_zero",
            "python_overhead",
            output_postprocess,
            latest_ms,
            latest_avg,
            queue_avg,
            False,
            "post-instrumentation overhead analysis",
            "not_primary",
        ),
        candidate(
            "final_output_postprocess_theoretical_zero",
            "python_overhead",
            final_output_postprocess,
            latest_ms,
            latest_avg,
            queue_avg,
            False,
            "post-instrumentation final segment output postprocess analysis",
            "not_primary",
        ),
        candidate(
            "seg27_28_last_token_logits_projection",
            "active_compute_or_output",
            final_projection,
            latest_ms,
            latest_avg,
            queue_avg,
            True,
            "final logits leverage model projection",
            "next_compile_then_runtime_validation_candidate",
        ),
        candidate(
            "perfect_hbm_group_load_residency",
            "memory_residency",
            hbm_group_load,
            latest_ms,
            latest_avg,
            queue_avg,
            False,
            "latest fixed group-load amortization; requires memory plan change",
            "capacity_or_residency_research_only",
        ),
        candidate(
            "final_projection_plus_perfect_hbm_residency",
            "combined_projection",
            final_projection + hbm_group_load,
            latest_ms,
            latest_avg,
            queue_avg,
            True,
            "sum of final-logits projection and perfect HBM residency ceiling",
            "still_requires_real_runtime_result",
        ),
    ]
    candidates.sort(
        key=lambda row: as_float(row.get("estimated_saved_ms_per_request")),
        reverse=True,
    )

    combined_small_overheads = (
        release_gap
        + nonhidden_python
        + hidden_materialize
        + input_prepare
        + output_postprocess
    )
    combined_final_and_small = final_projection + combined_small_overheads

    decision = {
        "queue_batch_remains_production_default": True,
        "true_batch_b4_is_research_artifact": True,
        "primary_next_code_target": "seg27_28_last_token_logits",
        "primary_next_code_target_saved_ms_per_request": round_or_none(final_projection),
        "small_python_and_gap_optimizations_combined_ms_per_request": round_or_none(
            combined_small_overheads
        ),
        "combined_final_plus_small_overhead_ms_per_request": round_or_none(
            combined_final_and_small
        ),
        "group_size_or_inner_order_current_primary_lever": group_inner_decision.get(
            "group_size_and_inner_order_are_current_primary_levers"
        ),
        "run_more_group_size_or_inner_order_sweeps_now": group_inner_decision.get(
            "run_more_group_size_or_inner_order_sweeps_now"
        ),
        "hbm_group_load_is_fixed_amortization_not_active_bpu_fix": hbm_decision.get(
            "hbm_group_load_is_fixed_amortization_not_active_bpu_fix",
            True,
        ),
        "projection_is_not_bpu_promotion_proof": True,
        "requires_real_runtime_result_before_promotion": True,
    }

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_bottleneck_closure_model",
        "source_paths": {
            "schedule": str(schedule_path),
            "group_switch": str(group_switch_path),
            "final_logits_leverage": str(final_logits_path),
            "post_instrumentation_overhead": str(post_overhead_path),
            "hbm_load": str(hbm_load_path),
            "group_inner_order_value_audit": str(group_inner_path),
        },
        "baseline": {
            "latest_b4_file": latest.get("file"),
            "latest_microbatch_count": latest.get("microbatch_count"),
            "latest_processed_request_count": latest.get("processed_request_count"),
            "latest_ms_per_request": latest_ms,
            "latest_avg_bpu_loading": latest_avg,
            "latest_avg_nonzero_bpu_loading": latest_nonzero,
            "queue_ms_per_request": queue_ms,
            "queue_avg_bpu_loading": queue_avg,
            "queue_avg_nonzero_bpu_loading": queue_nonzero,
            "latest_avg_bpu_gap_to_queue_points": round_or_none(latest_avg - queue_avg, 3),
            "latest_nonzero_bpu_gap_to_queue_points": round_or_none(
                latest_nonzero - queue_nonzero,
                3,
            ),
            "latest_required_nonzero_bpu_for_93_avg": bpu_gap.get(
                "latest_required_nonzero_bpu_for_93_avg"
            ),
            "latest_nonzero_shortfall_points_for_93_avg": bpu_gap.get(
                "latest_nonzero_shortfall_points"
            ),
            "projected_max_avg_bpu_if_nonzero_unchanged": bpu_gap.get(
                "projected_max_avg_bpu_if_nonzero_unchanged"
            ),
        },
        "components_ms_per_request": {
            "hbm_group_load": round_or_none(hbm_group_load),
            "release_plus_unaccounted_group_gap": round_or_none(release_gap),
            "group_switch_gap": round_or_none(group_switch_gap),
            "hidden_materialize": round_or_none(hidden_materialize),
            "nonhidden_python_segment_overhead": round_or_none(nonhidden_python),
            "input_prepare": round_or_none(input_prepare),
            "output_postprocess": round_or_none(output_postprocess),
            "final_output_postprocess": round_or_none(final_output_postprocess),
            "final_logits_excess_if_hidden_speed": round_or_none(final_excess),
            "final_logits_last_token_projection": round_or_none(final_projection),
        },
        "closure_candidates": candidates,
        "decision": decision,
        "interpretation": [
            "Small Python, release, and postprocess overheads are measurable but do not by themselves change the production decision.",
            "The only current latency target with multi-ms direct leverage is the seg27_28 final-logits last-token path.",
            "Perfect HBM group residency has a larger wall-time ceiling than small scheduler gaps, but it is a memory-residency research path and not active-BPU promotion proof.",
            "Group-size and inner-order sweeps remain blocked until final logits or memory-residency work changes the active runtime profile.",
        ],
    }


def render_markdown(payload: dict[str, Any], out_md: Path) -> None:
    baseline = payload["baseline"]
    components = payload["components_ms_per_request"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B=4 Bottleneck Closure Model",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        "",
        "## Baseline",
        "",
        f"- latest_b4_file: `{baseline['latest_b4_file']}`",
        f"- latest_microbatch_count: `{baseline['latest_microbatch_count']}`",
        f"- latest_ms_per_request: `{baseline['latest_ms_per_request']}`",
        f"- latest_avg_bpu_loading: `{baseline['latest_avg_bpu_loading']}`",
        f"- latest_avg_nonzero_bpu_loading: `{baseline['latest_avg_nonzero_bpu_loading']}`",
        f"- queue_avg_bpu_loading: `{baseline['queue_avg_bpu_loading']}`",
        f"- latest_avg_bpu_gap_to_queue_points: `{baseline['latest_avg_bpu_gap_to_queue_points']}`",
        f"- latest_nonzero_bpu_gap_to_queue_points: `{baseline['latest_nonzero_bpu_gap_to_queue_points']}`",
        f"- latest_required_nonzero_bpu_for_93_avg: `{baseline['latest_required_nonzero_bpu_for_93_avg']}`",
        f"- latest_nonzero_shortfall_points_for_93_avg: `{baseline['latest_nonzero_shortfall_points_for_93_avg']}`",
        "",
        "## Components",
        "",
    ]
    lines.extend(f"- {key}: `{value}` ms/request" for key, value in components.items())
    lines.extend(
        [
            "",
            "## Closure Candidates",
            "",
            "| candidate | saved ms/request | projected ms/request | wall-only avg BPU | decision |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["closure_candidates"]:
        lines.append(
            "| "
            f"{row['name']} | "
            f"{row['estimated_saved_ms_per_request']} | "
            f"{row['projected_ms_per_request']} | "
            f"{row['wall_only_projected_avg_bpu']} | "
            f"{row['decision']} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in decision.items())
    lines.extend(["", "## Interpretation", ""])
    lines.extend(f"- {item}" for item in payload["interpretation"])
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a conservative B=4 bottleneck closure model from existing telemetry."
    )
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args.analysis_root)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_markdown(payload, args.out_md)
    print(args.out_json)
    print(args.out_md)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
