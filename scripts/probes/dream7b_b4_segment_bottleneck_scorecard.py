#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_SEGMENT_DRAG = DEFAULT_ROOT / "dream7b_b4_segment_drag_breakdown_20260619.json"
DEFAULT_HBM_LOAD = DEFAULT_ROOT / "dream7b_b4_hbm_load_breakdown_20260619.json"
DEFAULT_FINAL_OUTPUT = DEFAULT_ROOT / "dream7b_b4_final_output_attribution_20260619.json"
DEFAULT_GROUP_SWITCH = DEFAULT_ROOT / "dream7b_b4_group_switch_accounting_20260619.json"
DEFAULT_GROUP_ORDER = DEFAULT_ROOT / "dream7b_b4_group_order_candidate_analysis_20260620.json"
DEFAULT_RUNTIME_BOUNDARY = DEFAULT_ROOT / "dream7b_b4_runtime_capacity_boundary_20260620.json"
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_segment_bottleneck_scorecard_20260620.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_segment_bottleneck_scorecard_20260620.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def round_or_none(value: float | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def find_segment_load(hbm_load: dict[str, Any], index: int) -> dict[str, Any]:
    latest = hbm_load.get("latest_default_run") or {}
    for row in latest.get("segment_load_rows") or []:
        row_index = row.get("index")
        if int(row_index if row_index is not None else -1) == index:
            return row
    return {}


def observed_variant_map(group_order: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("label")): row for row in group_order.get("observed_variants") or []}


def make_segment_rows(segment_drag: dict[str, Any], hbm_load: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in segment_drag.get("aggregate_segments_by_avg_run_ms") or []:
        raw_index = row.get("index")
        index = int(raw_index if raw_index is not None else -1)
        load = find_segment_load(hbm_load, index)
        run_excess = as_float(row.get("mean_positive_excess_ms_per_request"))
        load_ms_per_request = as_float(load.get("load_ms_per_request"))
        if index == 27:
            primary_risk = "final_logits_compute"
            action = "compile_or_runtime_path_that_reduces_final_logits_compute_or_avoids_full_vocab_output"
        elif index == 0:
            primary_risk = "token_embedding_load"
            action = "only_revisit_embedding_residency_after_final_logits_changes"
        else:
            primary_risk = "hidden_block_noise"
            action = "do_not_tune_hidden_order_without_new_load_residency_plan"
        rows.append(
            {
                "index": index,
                "kind": row.get("kind"),
                "representative_group": row.get("representative_group"),
                "observed_run_count": row.get("observed_run_count"),
                "mean_avg_run_ms": row.get("mean_avg_run_ms"),
                "stdev_avg_run_ms": row.get("stdev_avg_run_ms"),
                "mean_positive_excess_ms_per_request": row.get(
                    "mean_positive_excess_ms_per_request"
                ),
                "hbm_size_mib": load.get("hbm_size_mib"),
                "load_ms": load.get("load_ms"),
                "load_ms_per_request": load.get("load_ms_per_request"),
                "primary_risk": primary_risk,
                "recommended_action": action,
                "priority_score": round(run_excess * 10.0 + load_ms_per_request, 6),
            }
        )
    return sorted(rows, key=lambda row: as_float(row.get("priority_score")), reverse=True)


def make_group_tuning(group_order: dict[str, Any], group_switch: dict[str, Any]) -> dict[str, Any]:
    variants = observed_variant_map(group_order)
    non_baseline = [
        row
        for row in group_order.get("observed_variants") or []
        if row.get("status") == "observed"
        and as_float(row.get("delta_ms_per_request_vs_baseline")) != 0.0
    ]
    least_bad = min(
        non_baseline,
        key=lambda row: as_float(row.get("delta_ms_per_request_vs_baseline")),
        default={},
    )
    decision = group_order.get("decision") or {}
    switch_decision = group_switch.get("decision") or {}
    return {
        "baseline": group_order.get("baseline") or {},
        "least_bad_nonbaseline_variant": least_bad,
        "microbatch_major_delta_ms_per_request": (
            variants.get("mb512_microbatch_major_same_ranges") or {}
        ).get("delta_ms_per_request_vs_baseline"),
        "g6_even_delta_ms_per_request": (variants.get("mb512_segment_major_g6_even") or {}).get(
            "delta_ms_per_request_vs_baseline"
        ),
        "g7_even_delta_ms_per_request": (variants.get("mb512_segment_major_g7_even") or {}).get(
            "delta_ms_per_request_vs_baseline"
        ),
        "final_isolated_delta_ms_per_request": (
            variants.get("mb512_segment_major_final_isolated") or {}
        ).get("delta_ms_per_request_vs_baseline"),
        "no_observed_variant_beats_baseline": decision.get("no_observed_variant_beats_baseline"),
        "more_mb512_group_boundary_sweeps_deprioritized": decision.get(
            "more_mb512_group_boundary_sweeps_deprioritized"
        ),
        "group_release_and_unaccounted_gap_not_primary": switch_decision.get(
            "group_release_and_unaccounted_gap_not_primary"
        ),
        "recommended_group_policy": "keep_5_group_segment_major_default; use_g7_only_as_capacity_probe_if_memory_plan_changes",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    segment_drag = read_json(args.segment_drag_json)
    hbm_load = read_json(args.hbm_load_json)
    final_output = read_json(args.final_output_json)
    group_switch = read_json(args.group_switch_json)
    group_order = read_json(args.group_order_json)
    runtime_boundary = read_json(args.runtime_boundary_json)

    segment_rows = make_segment_rows(segment_drag, hbm_load)
    latest_focus = segment_drag.get("latest_default_focus") or {}
    default_stability = segment_drag.get("default_collect_stability") or {}
    all_stability = segment_drag.get("cross_run_stability") or {}
    final_row = next((row for row in segment_rows if row.get("index") == 27), {})
    token_row = next((row for row in segment_rows if row.get("index") == 0), {})
    hidden_rows = [row for row in segment_rows if row.get("kind") == "hidden_block"]
    max_hidden = hidden_rows[0] if hidden_rows else {}
    output_decision = final_output.get("decision") or {}
    boundary_summary = runtime_boundary.get("summary") or {}
    boundary_decision = runtime_boundary.get("decision") or {}

    action_priorities = [
        {
            "rank": 1,
            "action": "target_final_logits_compute_or_output_avoidance",
            "why": "final logits is the only large active-run outlier and full-output overhead outside runtime.run is small",
            "evidence": {
                "final_mean_excess_ms_per_request": final_row.get(
                    "mean_positive_excess_ms_per_request"
                ),
                "final_vs_hidden_mean_ratio": latest_focus.get("final_vs_hidden_mean_ratio"),
                "final_output_overhead_small": output_decision.get(
                    "b4_final_python_output_overhead_small"
                ),
                "recommended_next": output_decision.get("recommended_next"),
            },
        },
        {
            "rank": 2,
            "action": "keep_segment_major_5_group_default_for_current_memory_state",
            "why": "observed mb512 group/order variants are all slower than the 5-group segment-major baseline",
            "evidence": make_group_tuning(group_order, group_switch),
        },
        {
            "rank": 3,
            "action": "do_not_continue_gap_microbatch_sweeps_above_success_boundary",
            "why": "gap-instrumented B=4 succeeds at mb512 and fails first at mb768 in the current memory state",
            "evidence": {
                "latest_gap_success_microbatch_count": boundary_summary.get(
                    "latest_gap_success_microbatch_count"
                ),
                "first_gap_failure_microbatch_count": boundary_summary.get(
                    "first_gap_failure_microbatch_count"
                ),
                "stop_rule": boundary_decision.get(
                    "do_not_continue_gap_microbatch_sweeps_above_success_boundary"
                ),
            },
        },
        {
            "rank": 4,
            "action": "deprioritize_hidden_block_inner_order_tuning",
            "why": "hidden blocks are tightly clustered; the largest hidden excess is orders smaller than final logits",
            "evidence": {
                "max_hidden_index": max_hidden.get("index"),
                "max_hidden_mean_excess_ms_per_request": max_hidden.get(
                    "mean_positive_excess_ms_per_request"
                ),
                "final_to_max_hidden_excess_ratio": round_or_none(
                    as_float(final_row.get("mean_positive_excess_ms_per_request"))
                    / as_float(max_hidden.get("mean_positive_excess_ms_per_request"))
                    if as_float(max_hidden.get("mean_positive_excess_ms_per_request"))
                    else None,
                    3,
                ),
            },
        },
        {
            "rank": 5,
            "action": "treat_token_embedding_as_residency_followup_not_primary_runtime_fix",
            "why": "token embedding has high HBM load but small active-run excess versus hidden blocks",
            "evidence": {
                "token_load_ms_per_request": token_row.get("load_ms_per_request"),
                "token_mean_excess_ms_per_request": token_row.get(
                    "mean_positive_excess_ms_per_request"
                ),
                "token_to_final_active_excess_ratio": round_or_none(
                    as_float(token_row.get("mean_positive_excess_ms_per_request"))
                    / as_float(final_row.get("mean_positive_excess_ms_per_request"))
                    if as_float(final_row.get("mean_positive_excess_ms_per_request"))
                    else None,
                    4,
                ),
            },
        },
    ]

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_segment_bottleneck_scorecard",
        "source_paths": {
            "segment_drag": str(args.segment_drag_json),
            "hbm_load": str(args.hbm_load_json),
            "final_output": str(args.final_output_json),
            "group_switch": str(args.group_switch_json),
            "group_order": str(args.group_order_json),
            "runtime_boundary": str(args.runtime_boundary_json),
        },
        "latest_default_focus": {
            "file": latest_focus.get("file"),
            "microbatch_count": latest_focus.get("microbatch_count"),
            "ms_per_request": latest_focus.get("ms_per_request"),
            "avg_bpu_loading": latest_focus.get("avg_bpu_loading"),
            "avg_nonzero_bpu_loading": latest_focus.get("avg_nonzero_bpu_loading"),
            "final_vs_hidden_mean_ratio": latest_focus.get("final_vs_hidden_mean_ratio"),
            "final_excess_ms_per_request_if_hidden_speed": latest_focus.get(
                "final_excess_ms_per_request_if_hidden_speed"
            ),
            "token_excess_ms_per_request_if_hidden_speed": latest_focus.get(
                "token_excess_ms_per_request_if_hidden_speed"
            ),
        },
        "segment_stability": {
            "default_collect_run_count": segment_drag.get("default_collect_run_count"),
            "analyzed_run_count": segment_drag.get("analyzed_run_count"),
            "default_collect_final_excess_ms_per_request": (
                default_stability.get("final_excess_ms_per_request") or {}
            ),
            "default_collect_hidden_mean_avg_run_ms": (
                default_stability.get("hidden_mean_avg_run_ms") or {}
            ),
            "all_segment_major_final_excess_ms_per_request": (
                all_stability.get("final_excess_ms_per_request") or {}
            ),
            "all_segment_major_hidden_mean_avg_run_ms": (
                all_stability.get("hidden_mean_avg_run_ms") or {}
            ),
        },
        "segment_bottlenecks": segment_rows[:10],
        "group_tuning": make_group_tuning(group_order, group_switch),
        "runtime_boundary": {
            "latest_gap_success_microbatch_count": boundary_summary.get(
                "latest_gap_success_microbatch_count"
            ),
            "first_gap_failure_microbatch_count": boundary_summary.get(
                "first_gap_failure_microbatch_count"
            ),
            "latest_successful_microbatch_count": boundary_summary.get(
                "latest_successful_microbatch_count"
            ),
            "do_not_continue_gap_microbatch_sweeps_above_success_boundary": boundary_decision.get(
                "do_not_continue_gap_microbatch_sweeps_above_success_boundary"
            ),
        },
        "action_priorities": action_priorities,
        "decision": {
            "primary_runtime_lever": "final_logits_compute_or_output_avoidance",
            "secondary_residency_lever": "token_embedding_or_final_hbm_residency_only_after_memory_plan_changes",
            "preferred_inner_order": "segment-major",
            "preferred_group_policy": "5_group_segment_major_default",
            "avoid_more_mb512_boundary_sweeps": True,
            "avoid_gap_microbatch_sweeps_above_mb512": True,
            "next_runtime_candidate": "seg27_28_last_token_logits",
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dream7B B4 Segment Bottleneck Scorecard",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- primary_runtime_lever: {payload['decision']['primary_runtime_lever']}",
        f"- preferred_group_policy: {payload['decision']['preferred_group_policy']}",
        f"- next_runtime_candidate: {payload['decision']['next_runtime_candidate']}",
        "",
        "## Latest Default Focus",
        "",
    ]
    for key, value in payload["latest_default_focus"].items():
        lines.append(f"- {key}: `{value}`")
    stability = payload["segment_stability"]
    default_final = stability["default_collect_final_excess_ms_per_request"]
    all_final = stability["all_segment_major_final_excess_ms_per_request"]
    lines.extend(
        [
            "",
            "## Segment Stability",
            "",
            f"- default_collect_run_count: `{stability['default_collect_run_count']}`",
            f"- analyzed_run_count: `{stability['analyzed_run_count']}`",
            f"- default_collect_final_excess_mean_ms_per_request: `{default_final.get('mean')}`",
            f"- default_collect_final_excess_stdev_ms_per_request: `{default_final.get('stdev')}`",
            f"- all_segment_major_final_excess_mean_ms_per_request: `{all_final.get('mean')}`",
            f"- all_segment_major_final_excess_stdev_ms_per_request: `{all_final.get('stdev')}`",
        ]
    )
    lines.extend(
        [
            "",
            "## Top Segment Bottlenecks",
            "",
            "| rank | index | kind | group | run excess ms/request | load ms/request | priority | action |",
            "| ---: | ---: | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for rank, row in enumerate(payload["segment_bottlenecks"][:8], start=1):
        lines.append(
            "| "
            f"{rank} | {row.get('index')} | {row.get('kind')} | {row.get('representative_group')} | "
            f"{row.get('mean_positive_excess_ms_per_request')} | {row.get('load_ms_per_request')} | "
            f"{row.get('priority_score')} | {row.get('recommended_action')} |"
        )
    group = payload["group_tuning"]
    lines.extend(
        [
            "",
            "## Group / Inner-Order Decision",
            "",
            f"- baseline: `{(group.get('baseline') or {}).get('group_ranges')}`",
            f"- microbatch_major_delta_ms_per_request: `{group.get('microbatch_major_delta_ms_per_request')}`",
            f"- g6_even_delta_ms_per_request: `{group.get('g6_even_delta_ms_per_request')}`",
            f"- g7_even_delta_ms_per_request: `{group.get('g7_even_delta_ms_per_request')}`",
            f"- final_isolated_delta_ms_per_request: `{group.get('final_isolated_delta_ms_per_request')}`",
            f"- no_observed_variant_beats_baseline: `{group.get('no_observed_variant_beats_baseline')}`",
            f"- recommended_group_policy: `{group.get('recommended_group_policy')}`",
            "",
            "## Action Priorities",
            "",
        ]
    )
    for item in payload["action_priorities"]:
        lines.append(f"{item['rank']}. `{item['action']}` - {item['why']}")
    lines.extend(["", "## Source Paths", ""])
    for key, value in payload["source_paths"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a B=4 segment-level bottleneck and tuning scorecard from existing telemetry."
    )
    parser.add_argument("--segment-drag-json", type=Path, default=DEFAULT_SEGMENT_DRAG)
    parser.add_argument("--hbm-load-json", type=Path, default=DEFAULT_HBM_LOAD)
    parser.add_argument("--final-output-json", type=Path, default=DEFAULT_FINAL_OUTPUT)
    parser.add_argument("--group-switch-json", type=Path, default=DEFAULT_GROUP_SWITCH)
    parser.add_argument("--group-order-json", type=Path, default=DEFAULT_GROUP_ORDER)
    parser.add_argument("--runtime-boundary-json", type=Path, default=DEFAULT_RUNTIME_BOUNDARY)
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
