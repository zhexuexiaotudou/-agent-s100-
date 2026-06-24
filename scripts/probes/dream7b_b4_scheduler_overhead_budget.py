#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_GROUP_SWITCH = DEFAULT_ROOT / "dream7b_b4_group_switch_accounting_20260619.json"
DEFAULT_FINAL_OUTPUT = DEFAULT_ROOT / "dream7b_b4_final_output_attribution_20260619.json"
DEFAULT_HBM_LOAD = DEFAULT_ROOT / "dream7b_b4_hbm_load_breakdown_20260619.json"
DEFAULT_GROUP_ORDER = DEFAULT_ROOT / "dream7b_b4_group_order_candidate_analysis_20260620.json"
DEFAULT_RUNTIME_BOUNDARY = DEFAULT_ROOT / "dream7b_b4_runtime_capacity_boundary_20260620.json"
DEFAULT_SEGMENT_SCORECARD = DEFAULT_ROOT / "dream7b_b4_segment_bottleneck_scorecard_20260620.json"
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_scheduler_overhead_budget_20260620.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_scheduler_overhead_budget_20260620.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def ratio(numerator: Any, denominator: Any, digits: int = 3) -> float | None:
    num = as_float(numerator)
    den = as_float(denominator)
    if num is None or den in (None, 0.0):
        return None
    return round(num / den, digits)


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None else None


def budget_row(
    name: str,
    ms_per_request: Any,
    category: str,
    code_target: str,
    recommendation: str,
    denominator: Any,
) -> dict[str, Any]:
    value = as_float(ms_per_request)
    den = as_float(denominator)
    return {
        "name": name,
        "ms_per_request": round_or_none(value),
        "share_of_wall": round_or_none(value / den if value is not None and den else None),
        "category": category,
        "code_target": code_target,
        "recommendation": recommendation,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    group_switch = read_json(args.group_switch_json)
    final_output = read_json(args.final_output_json)
    hbm_load = read_json(args.hbm_load_json)
    group_order = read_json(args.group_order_json)
    runtime_boundary = read_json(args.runtime_boundary_json)
    segment_scorecard = read_json(args.segment_scorecard_json)

    default_summary = group_switch.get("latest_default_summary") or {}
    gap_summary = group_switch.get("latest_gap_instrumented_summary") or {}
    final_default = final_output.get("latest_default_b4") or {}
    hbm_default = hbm_load.get("latest_default_run") or {}
    group_decision = group_order.get("decision") or {}
    boundary_summary = runtime_boundary.get("summary") or {}
    boundary_decision = runtime_boundary.get("decision") or {}
    scorecard_decision = segment_scorecard.get("decision") or {}

    wall_ms = default_summary.get("ms_per_request")
    final_excess = default_summary.get("final_logits_excess_ms_per_request_if_hidden_speed")
    final_run = default_summary.get("final_logits_run_ms_per_request")
    final_python_overhead = final_default.get("final_segment_overhead_ms_per_request")
    hidden_materialize = default_summary.get("hidden_materialize_ms_per_request")
    segment_overhead_no_hidden = default_summary.get(
        "segment_overhead_excluding_hidden_materialize_ms_per_request"
    )
    default_group_switch_gap = default_summary.get("group_switch_gap_ms_per_request")
    release_gap = default_summary.get("group_release_ms_per_request")
    unaccounted_gap = default_summary.get("unaccounted_gap_ms_per_request")
    gap_residual = gap_summary.get("segment_overhead_excluding_measured_gaps_ms_per_request")
    inter_segment_gap = gap_summary.get("inter_segment_first_run_gap_ms_per_request")
    intra_segment_gap = gap_summary.get("intra_segment_run_gap_ms_per_request")
    group_load = default_summary.get("group_load_ms_per_request")
    total_hbm_load = hbm_default.get("total_group_load_ms_per_request")
    final_hbm_load = hbm_default.get("final_load_ms")
    token_hbm_load = hbm_default.get("token_load_ms")

    rows = [
        budget_row(
            "final_logits_active_excess",
            final_excess,
            "primary_runtime_compute",
            "compile_or_runtime_final_logits_mode",
            "implement_or_validate last-token/full-vocab-output avoidance before scheduler micro-tuning",
            wall_ms,
        ),
        budget_row(
            "final_logits_run",
            final_run,
            "primary_runtime_compute",
            "seg27_28 runtime.run",
            "track as upper bound for final-logits optimization impact",
            wall_ms,
        ),
        budget_row(
            "hidden_materialize",
            hidden_materialize,
            "secondary_python_memory",
            "hidden buffer reuse/preallocation",
            "only optimize after final logits path; prior prealloc evidence should remain experimental",
            wall_ms,
        ),
        budget_row(
            "segment_overhead_excluding_hidden_materialize",
            segment_overhead_no_hidden,
            "secondary_python_scheduler",
            "segment loop bookkeeping and tensor handoff",
            "profile locally, but expected ceiling is far below final logits excess",
            wall_ms,
        ),
        budget_row(
            "gap_instrumented_residual_after_measured_gaps",
            gap_residual,
            "secondary_python_scheduler",
            "gap-field residual scheduler overhead",
            "use for instrumentation sanity; do not chase above mb512 until memory plan changes",
            gap_summary.get("ms_per_request"),
        ),
        budget_row(
            "intra_segment_run_gap",
            intra_segment_gap,
            "low_priority_python_gap",
            "per-segment repeated runtime.run dispatch spacing",
            "deprioritize unless a cheap batching/refactor removes it without memory risk",
            gap_summary.get("ms_per_request"),
        ),
        budget_row(
            "inter_segment_first_run_gap",
            inter_segment_gap,
            "low_priority_python_gap",
            "segment transition dispatch spacing",
            "already negligible in gap-instrumented run",
            gap_summary.get("ms_per_request"),
        ),
        budget_row(
            "group_switch_gap",
            default_group_switch_gap,
            "low_priority_group_switch",
            "group transition scheduling",
            "do not optimize before final logits; measured switch gap is tiny",
            wall_ms,
        ),
        budget_row(
            "group_release",
            release_gap,
            "low_priority_group_release",
            "release_gc policy",
            "skip-GC remains profiling only until longer-run evidence changes",
            wall_ms,
        ),
        budget_row(
            "unaccounted_group_gap",
            unaccounted_gap,
            "low_priority_group_switch",
            "unaccounted group transition",
            "too small to explain BPU gap",
            wall_ms,
        ),
        budget_row(
            "group_hbm_load_amortization",
            group_load,
            "fixed_hbm_load_amortization",
            "HBM residency/load cache",
            "not an active BPU fix; revisit only with a memory plan that keeps more groups resident",
            wall_ms,
        ),
    ]

    by_name = {row["name"]: row for row in rows}
    group_switch_gap_ratio = ratio(final_excess, default_group_switch_gap)
    intra_gap_ratio = ratio(final_excess, intra_segment_gap)
    residual_ratio = ratio(final_excess, gap_residual)
    final_python_overhead_ratio = ratio(final_excess, final_python_overhead)

    code_priorities = [
        {
            "rank": 1,
            "target": "seg27_28_last_token_logits_or_output_avoidance",
            "expected_ceiling_ms_per_request": final_excess,
            "evidence": "final logits active excess is larger than measured scheduler gaps by one to two orders of magnitude",
            "status": "next_runtime_candidate",
        },
        {
            "rank": 2,
            "target": "hidden_buffer_reuse_or_preallocation_cleanup",
            "expected_ceiling_ms_per_request": hidden_materialize,
            "evidence": "hidden materialization is visible but previous prealloc evidence does not justify promotion yet",
            "status": "instrumentation_or_local_refactor_only",
        },
        {
            "rank": 3,
            "target": "segment_loop_bookkeeping_tightening",
            "expected_ceiling_ms_per_request": segment_overhead_no_hidden,
            "evidence": "segment overhead excluding hidden materialize is measurable but much smaller than final logits",
            "status": "only_after_final_logits_candidate",
        },
        {
            "rank": 4,
            "target": "group_switch_or_release_micro_tuning",
            "expected_ceiling_ms_per_request": default_group_switch_gap,
            "evidence": "group switch gap is tiny versus final logits excess",
            "status": "deprioritized",
        },
    ]

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_scheduler_overhead_budget",
        "source_paths": {
            "group_switch": str(args.group_switch_json),
            "final_output": str(args.final_output_json),
            "hbm_load": str(args.hbm_load_json),
            "group_order": str(args.group_order_json),
            "runtime_boundary": str(args.runtime_boundary_json),
            "segment_scorecard": str(args.segment_scorecard_json),
        },
        "baseline": {
            "file": default_summary.get("file"),
            "microbatch_count": default_summary.get("microbatch_count"),
            "processed_request_count": default_summary.get("processed_request_count"),
            "ms_per_request": wall_ms,
            "avg_bpu_loading": default_summary.get("avg_bpu_loading"),
            "avg_nonzero_bpu_loading": default_summary.get("avg_nonzero_bpu_loading"),
        },
        "gap_instrumented_reference": {
            "file": gap_summary.get("file"),
            "microbatch_count": gap_summary.get("microbatch_count"),
            "ms_per_request": gap_summary.get("ms_per_request"),
            "avg_bpu_loading": gap_summary.get("avg_bpu_loading"),
        },
        "budget_rows": rows,
        "ratios": {
            "final_excess_to_group_switch_gap": group_switch_gap_ratio,
            "final_excess_to_intra_segment_gap": intra_gap_ratio,
            "final_excess_to_gap_residual": residual_ratio,
            "final_excess_to_final_python_output_overhead": final_python_overhead_ratio,
        },
        "hbm_context": {
            "mb128_total_hbm_load_ms_per_request": total_hbm_load,
            "mb128_final_hbm_load_ms": final_hbm_load,
            "mb128_token_hbm_load_ms": token_hbm_load,
            "largest_load_group": (hbm_load.get("decision") or {}).get("largest_load_group"),
            "final_group_is_largest_load_group": (hbm_load.get("decision") or {}).get(
                "final_group_is_largest_load_group"
            ),
        },
        "group_order_context": {
            "preferred_inner_order": scorecard_decision.get("preferred_inner_order"),
            "preferred_group_policy": scorecard_decision.get("preferred_group_policy"),
            "no_observed_variant_beats_baseline": group_decision.get(
                "no_observed_variant_beats_baseline"
            ),
            "best_nonbaseline_delta_ms_per_request": group_decision.get(
                "best_nonbaseline_observed_variant_delta_ms_per_request"
            ),
            "more_mb512_group_boundary_sweeps_deprioritized": group_decision.get(
                "more_mb512_group_boundary_sweeps_deprioritized"
            ),
        },
        "capacity_stop_rule": {
            "latest_gap_success_microbatch_count": boundary_summary.get(
                "latest_gap_success_microbatch_count"
            ),
            "first_gap_failure_microbatch_count": boundary_summary.get(
                "first_gap_failure_microbatch_count"
            ),
            "do_not_continue_gap_microbatch_sweeps_above_success_boundary": boundary_decision.get(
                "do_not_continue_gap_microbatch_sweeps_above_success_boundary"
            ),
        },
        "code_priorities": code_priorities,
        "decision": {
            "primary_code_target": code_priorities[0]["target"],
            "deprioritize_python_inter_segment_gap_tuning": True,
            "deprioritize_more_group_boundary_sweeps": True,
            "queue_batch_remains_default": True,
            "next_runtime_experiment": "validate seg27_28 last-token logits or equivalent full-vocab-output avoidance at mb512 before larger sweeps",
        },
        "sanity_checks": {
            "final_excess_exceeds_group_switch_gap_50x": (
                group_switch_gap_ratio is not None and group_switch_gap_ratio >= 50
            ),
            "final_excess_exceeds_intra_segment_gap_20x": (
                intra_gap_ratio is not None and intra_gap_ratio >= 20
            ),
            "group_order_variants_do_not_beat_baseline": group_decision.get(
                "no_observed_variant_beats_baseline"
            )
            is True,
            "gap_sweeps_above_mb512_blocked": boundary_decision.get(
                "do_not_continue_gap_microbatch_sweeps_above_success_boundary"
            )
            is True,
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dream7B B4 Scheduler Overhead Budget",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- baseline: `{payload['baseline']['microbatch_count']}` microbatches, `{payload['baseline']['ms_per_request']}` ms/request, avg BPU `{payload['baseline']['avg_bpu_loading']}`",
        f"- primary_code_target: `{payload['decision']['primary_code_target']}`",
        f"- next_runtime_experiment: `{payload['decision']['next_runtime_experiment']}`",
        "",
        "## Budget Rows",
        "",
        "| name | ms/request | wall share | category | code target | recommendation |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["budget_rows"]:
        share = row["share_of_wall"]
        share_text = f"{share:.4f}" if isinstance(share, float) else ""
        lines.append(
            "| "
            f"{row['name']} | {row['ms_per_request']} | {share_text} | "
            f"{row['category']} | {row['code_target']} | {row['recommendation']} |"
        )
    lines.extend(
        [
            "",
            "## Ratios",
            "",
        ]
    )
    for key, value in payload["ratios"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Code Priorities", ""])
    for item in payload["code_priorities"]:
        lines.append(
            f"{item['rank']}. `{item['target']}`: ceiling `{item['expected_ceiling_ms_per_request']}` ms/request; {item['status']}; {item['evidence']}."
        )
    lines.extend(
        [
            "",
            "## Stop Rules",
            "",
            f"- deprioritize_python_inter_segment_gap_tuning: `{payload['decision']['deprioritize_python_inter_segment_gap_tuning']}`",
            f"- deprioritize_more_group_boundary_sweeps: `{payload['decision']['deprioritize_more_group_boundary_sweeps']}`",
            f"- latest_gap_success_microbatch_count: `{payload['capacity_stop_rule']['latest_gap_success_microbatch_count']}`",
            f"- first_gap_failure_microbatch_count: `{payload['capacity_stop_rule']['first_gap_failure_microbatch_count']}`",
            "",
            "## Source Paths",
            "",
        ]
    )
    for key, value in payload["source_paths"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a B=4 scheduler overhead budget from existing Dream7B telemetry."
    )
    parser.add_argument("--group-switch-json", type=Path, default=DEFAULT_GROUP_SWITCH)
    parser.add_argument("--final-output-json", type=Path, default=DEFAULT_FINAL_OUTPUT)
    parser.add_argument("--hbm-load-json", type=Path, default=DEFAULT_HBM_LOAD)
    parser.add_argument("--group-order-json", type=Path, default=DEFAULT_GROUP_ORDER)
    parser.add_argument("--runtime-boundary-json", type=Path, default=DEFAULT_RUNTIME_BOUNDARY)
    parser.add_argument("--segment-scorecard-json", type=Path, default=DEFAULT_SEGMENT_SCORECARD)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(args.out_md)
    print(args.out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
