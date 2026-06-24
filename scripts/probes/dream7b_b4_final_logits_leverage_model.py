#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def pct(part: float | None, whole: float | None) -> float | None:
    value = ratio(part, whole)
    if value is None:
        return None
    return value * 100.0


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    sizing = read_json(args.sizing_json)
    scaling = read_json(args.scaling_json)
    compare = read_json(args.validation_compare_json)
    group_switch = read_json(args.group_switch_json)

    latest = scaling.get("latest_observed") or {}
    asymptotic = scaling.get("asymptotic_projection") or {}
    current = sizing.get("current") or {}
    candidate = sizing.get("last_token_logits_candidate") or {}
    compare_decision = compare.get("decision") or {}
    thresholds = compare.get("thresholds") or {}
    baseline = compare.get("baseline") or {}

    latest_ms = as_float(latest.get("ms_per_request"))
    saved_ms = as_float(candidate.get("projection_only_hypothesis_saved_ms_per_request"))
    final_excess = as_float(current.get("final_excess_ms_per_request_if_hidden_speed"))
    final_run = as_float(current.get("final_run_ms_per_request"))
    final_overhead = as_float(current.get("final_segment_overhead_ms_per_request"))
    projected_ms = latest_ms - saved_ms if latest_ms is not None and saved_ms is not None else None
    baseline_ms = as_float(baseline.get("ms_per_request"))
    baseline_projected_ms = baseline_ms - saved_ms if baseline_ms is not None and saved_ms is not None else None

    latest_nonzero = as_float(latest.get("avg_nonzero_bpu_loading"))
    latest_avg = as_float(latest.get("avg_bpu_loading"))
    latest_required_nonzero = as_float(latest.get("required_nonzero_bpu_for_93_avg"))
    low_load_required_nonzero = as_float(
        asymptotic.get("required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction")
    )
    projected_max_avg = as_float(asymptotic.get("projected_max_avg_bpu_if_nonzero_unchanged"))

    final_capture_ratio = ratio(saved_ms, final_excess)
    latency_reduction_pct_latest = pct(saved_ms, latest_ms)
    latency_reduction_pct_baseline = pct(saved_ms, baseline_ms)
    final_run_reduction_pct = pct(saved_ms, final_run)
    final_output_overhead_fraction_of_saved = ratio(final_overhead, saved_ms)
    switch_gap = as_float(group_switch.get("latest_default_summary", {}).get("group_switch_gap_ms_per_request"))
    if switch_gap is None:
        switch_gap = as_float(group_switch.get("group_switch_gap_ms_per_request"))

    bpu_shortfalls = {
        "latest_required_nonzero_bpu_for_93_avg": latest_required_nonzero,
        "latest_nonzero_bpu": latest_nonzero,
        "latest_nonzero_shortfall_points": round_or_none(
            latest_required_nonzero - latest_nonzero
            if latest_required_nonzero is not None and latest_nonzero is not None
            else None,
            3,
        ),
        "low_load_required_nonzero_bpu_for_93_avg": low_load_required_nonzero,
        "low_load_nonzero_shortfall_points": round_or_none(
            low_load_required_nonzero - latest_nonzero
            if low_load_required_nonzero is not None and latest_nonzero is not None
            else None,
            3,
        ),
        "projected_max_avg_bpu_if_nonzero_unchanged": projected_max_avg,
        "projected_max_still_below_93": asymptotic.get("projected_max_still_below_93"),
    }

    decision = {
        "primary_candidate": "seg27_28_last_token_logits",
        "candidate_type": "single_segment_compile_then_mb512_validation",
        "projection_closes_most_final_logits_excess": bool(final_capture_ratio is not None and final_capture_ratio >= 0.8),
        "projection_is_latency_meaningful": bool(saved_ms is not None and saved_ms >= 1.0),
        "projection_is_not_bpu_promotion_proof": True,
        "do_not_promote_without_runtime_result": True,
        "do_not_run_standard_group_or_inner_order_sweeps": True,
        "next_gate": "compile_manifest_verification_then_mb512_runtime_validation",
        "current_compare_decision": compare_decision.get("decision"),
    }

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_final_logits_leverage_model",
        "source_paths": {
            "sizing": str(args.sizing_json),
            "scaling": str(args.scaling_json),
            "validation_compare": str(args.validation_compare_json),
            "group_switch": str(args.group_switch_json),
        },
        "current": {
            "latest_microbatch_count": latest.get("microbatch_count"),
            "latest_ms_per_request": latest_ms,
            "latest_avg_bpu_loading": latest_avg,
            "latest_avg_nonzero_bpu_loading": latest_nonzero,
            "current_final_shape": current.get("final_shape"),
            "candidate_target_shape": candidate.get("target_shape"),
            "output_element_reduction_vs_current": candidate.get("output_element_reduction_vs_current"),
        },
        "leverage": {
            "projection_saved_ms_per_request": saved_ms,
            "final_excess_ms_per_request_if_hidden_speed": final_excess,
            "projection_capture_of_final_excess_ratio": round_or_none(final_capture_ratio, 6),
            "projection_capture_of_final_excess_pct": round_or_none(
                final_capture_ratio * 100.0 if final_capture_ratio is not None else None,
                3,
            ),
            "latest_projected_ms_per_request_if_saved": round_or_none(projected_ms, 6),
            "latest_projected_latency_reduction_pct": round_or_none(latency_reduction_pct_latest, 3),
            "mb512_baseline_ms_per_request": baseline_ms,
            "mb512_projected_ms_per_request_if_saved": round_or_none(baseline_projected_ms, 6),
            "mb512_projected_latency_reduction_pct": round_or_none(latency_reduction_pct_baseline, 3),
            "final_run_ms_per_request": final_run,
            "final_run_reduction_pct_if_projection_holds": round_or_none(final_run_reduction_pct, 3),
            "final_segment_overhead_ms_per_request": final_overhead,
            "final_output_overhead_fraction_of_saved": round_or_none(final_output_overhead_fraction_of_saved, 6),
            "group_switch_gap_ms_per_request": switch_gap,
            "projection_saved_to_group_switch_gap_ratio": round_or_none(ratio(saved_ms, switch_gap), 3),
        },
        "bpu_promotion_gap": bpu_shortfalls,
        "validation_thresholds": {
            "min_wall_improvement_ms_per_request": thresholds.get("min_wall_improvement_ms_per_request"),
            "min_final_run_improvement_ms_per_request": thresholds.get(
                "min_final_run_improvement_ms_per_request"
            ),
            "max_nonzero_bpu_regression_points": thresholds.get("max_nonzero_bpu_regression_points"),
            "candidate_result_exists": compare.get("candidate", {}).get("exists"),
            "candidate_compare_decision": compare_decision.get("decision"),
        },
        "decision": decision,
        "interpretation": [
            "The last-token final-logits candidate has a roughly 3 ms/request projection ceiling, so it is the only current code path with a material latency ceiling.",
            "The projection mostly captures the measured final-logits excess, but it does not estimate active/nonzero BPU improvement.",
            "Average-BPU promotion still requires a real runtime result because the latest nonzero BPU remains below the level required for a 93 average even after fixed-load amortization.",
            "Standard group-count and inner-order sweeps remain lower-value until this final-logits path changes the active runtime profile.",
        ],
    }
    return payload


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    cur = payload["current"]
    lev = payload["leverage"]
    bpu = payload["bpu_promotion_gap"]
    thresholds = payload["validation_thresholds"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B4 Final-Logits Leverage Model",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- primary_candidate: `{decision['primary_candidate']}`",
        f"- current_compare_decision: `{decision['current_compare_decision']}`",
        "",
        "## Current Point",
        "",
        f"- latest_microbatch_count: `{cur['latest_microbatch_count']}`",
        f"- latest_ms_per_request: `{cur['latest_ms_per_request']}`",
        f"- latest_avg_bpu_loading: `{cur['latest_avg_bpu_loading']}`",
        f"- latest_avg_nonzero_bpu_loading: `{cur['latest_avg_nonzero_bpu_loading']}`",
        f"- current_final_shape: `{cur['current_final_shape']}`",
        f"- candidate_target_shape: `{cur['candidate_target_shape']}`",
        f"- output_element_reduction_vs_current: `{cur['output_element_reduction_vs_current']}`",
        "",
        "## Leverage",
        "",
        f"- projection_saved_ms_per_request: `{lev['projection_saved_ms_per_request']}`",
        f"- final_excess_ms_per_request_if_hidden_speed: `{lev['final_excess_ms_per_request_if_hidden_speed']}`",
        f"- projection_capture_of_final_excess_pct: `{lev['projection_capture_of_final_excess_pct']}`",
        f"- latest_projected_ms_per_request_if_saved: `{lev['latest_projected_ms_per_request_if_saved']}`",
        f"- latest_projected_latency_reduction_pct: `{lev['latest_projected_latency_reduction_pct']}`",
        f"- mb512_projected_ms_per_request_if_saved: `{lev['mb512_projected_ms_per_request_if_saved']}`",
        f"- mb512_projected_latency_reduction_pct: `{lev['mb512_projected_latency_reduction_pct']}`",
        f"- final_run_reduction_pct_if_projection_holds: `{lev['final_run_reduction_pct_if_projection_holds']}`",
        f"- final_output_overhead_fraction_of_saved: `{lev['final_output_overhead_fraction_of_saved']}`",
        f"- projection_saved_to_group_switch_gap_ratio: `{lev['projection_saved_to_group_switch_gap_ratio']}`",
        "",
        "## BPU Promotion Gap",
        "",
        f"- latest_required_nonzero_bpu_for_93_avg: `{bpu['latest_required_nonzero_bpu_for_93_avg']}`",
        f"- latest_nonzero_bpu: `{bpu['latest_nonzero_bpu']}`",
        f"- latest_nonzero_shortfall_points: `{bpu['latest_nonzero_shortfall_points']}`",
        f"- low_load_required_nonzero_bpu_for_93_avg: `{bpu['low_load_required_nonzero_bpu_for_93_avg']}`",
        f"- low_load_nonzero_shortfall_points: `{bpu['low_load_nonzero_shortfall_points']}`",
        f"- projected_max_avg_bpu_if_nonzero_unchanged: `{bpu['projected_max_avg_bpu_if_nonzero_unchanged']}`",
        f"- projected_max_still_below_93: `{bpu['projected_max_still_below_93']}`",
        "",
        "## Validation Gate",
        "",
        f"- min_wall_improvement_ms_per_request: `{thresholds['min_wall_improvement_ms_per_request']}`",
        f"- min_final_run_improvement_ms_per_request: `{thresholds['min_final_run_improvement_ms_per_request']}`",
        f"- max_nonzero_bpu_regression_points: `{thresholds['max_nonzero_bpu_regression_points']}`",
        f"- candidate_result_exists: `{thresholds['candidate_result_exists']}`",
        "",
        "## Decision",
        "",
    ]
    for key, value in decision.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Interpretation", ""])
    lines.extend(f"- {item}" for item in payload["interpretation"])
    lines.extend(["", "## Source Paths", ""])
    for key, value in payload["source_paths"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Quantify the B4 final-logits last-token candidate leverage without running compile/runtime."
    )
    parser.add_argument(
        "--sizing-json",
        type=Path,
        default=DEFAULT_ROOT / "dream7b_b4_final_logits_candidate_sizing_20260619.json",
    )
    parser.add_argument(
        "--scaling-json",
        type=Path,
        default=DEFAULT_ROOT / "dream7b_b4_scaling_saturation_analysis_20260619.json",
    )
    parser.add_argument(
        "--validation-compare-json",
        type=Path,
        default=DEFAULT_ROOT / "dream7b_b4_last_token_validation_compare_20260620.json",
    )
    parser.add_argument(
        "--group-switch-json",
        type=Path,
        default=DEFAULT_ROOT / "dream7b_b4_group_switch_accounting_20260619.json",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out-stem", default="dream7b_b4_final_logits_leverage_model_20260621")
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.out_dir / f"{args.out_stem}.json"
    out_md = args.out_dir / f"{args.out_stem}.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(out_md, payload)
    print(out_json)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
