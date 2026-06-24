#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_CANDIDATE = Path(
    "tmp/remote_true_batch_reports/"
    "b4_mb512_segment_major_last_token_true_batch_group_major_telemetry.json"
)
DEFAULT_BASELINE = Path(
    "tmp/remote_true_batch_reports/"
    "b4_mb512_segment_major_gap_fields_true_batch_group_major_telemetry.json"
)
DEFAULT_PLAN = DEFAULT_ROOT / "dream7b_b4_last_token_runtime_validation_plan_20260620.json"
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_last_token_validation_compare_20260620.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_last_token_validation_compare_20260620.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def group_label(group: dict[str, Any]) -> str:
    if "group_start" in group or "group_end" in group:
        return f"{group.get('group_start')}:{group.get('group_end')}"
    return f"{group.get('start')}:{group.get('end')}"


def group_ranges(payload: dict[str, Any]) -> list[str]:
    if payload.get("group_rows"):
        return [group_label(group) for group in payload.get("group_rows") or []]
    return [group_label(group) for group in payload.get("groups") or []]


def final_segment_row(payload: dict[str, Any]) -> dict[str, Any]:
    for group in payload.get("group_rows") or []:
        for row in group.get("segment_rows") or []:
            if as_int(row.get("index")) == 27:
                return row
    return {}


def output_shapes(row: dict[str, Any]) -> list[list[int]]:
    shapes: list[list[int]] = []
    for item in row.get("preview") or []:
        shape = item.get("output_shape")
        if isinstance(shape, list):
            shapes.append(shape)
    return shapes


def metric_delta(candidate: dict[str, Any], baseline: dict[str, Any], key: str) -> float | None:
    left = as_float(candidate.get(key))
    right = as_float(baseline.get(key))
    if left is None or right is None:
        return None
    return left - right


def final_run_ms_per_request(payload: dict[str, Any]) -> float | None:
    row = final_segment_row(payload)
    total_run = as_float(row.get("total_run_ms"))
    processed = as_int(payload.get("processed_request_count"))
    if total_run is None or not processed:
        return None
    return total_run / processed


def final_avg_run_ms(payload: dict[str, Any]) -> float | None:
    return as_float(final_segment_row(payload).get("avg_run_ms"))


def summarize_run(path: Path | None, payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "path": str(path) if path else None,
            "exists": False,
        }
    row = final_segment_row(payload)
    return {
        "path": str(path) if path else None,
        "exists": True,
        "verdict": payload.get("verdict"),
        "microbatch_count": payload.get("microbatch_count"),
        "batch_size": payload.get("batch_size"),
        "processed_request_count": payload.get("processed_request_count"),
        "failed_job_count": payload.get("failed_job_count"),
        "inner_order": payload.get("inner_order"),
        "group_ranges": group_ranges(payload),
        "final_logits_mode": payload.get("final_logits_mode"),
        "final_shape": payload.get("final_shape"),
        "expected_final_shape": payload.get("expected_final_shape"),
        "final_preview_output_shapes": output_shapes(row),
        "ms_per_request": payload.get("amortized_wall_ms_per_request"),
        "avg_bpu_loading": payload.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": payload.get("avg_nonzero_bpu_loading"),
        "final_avg_run_ms": round_or_none(final_avg_run_ms(payload), 6),
        "final_run_ms_per_request": round_or_none(final_run_ms_per_request(payload), 6),
    }


def all_shapes_match(shapes: list[list[int]], expected: list[int]) -> bool:
    return bool(shapes) and all(shape == expected for shape in shapes)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    plan = load_json(args.plan_json)
    expected = plan.get("expected") or {}
    expected_shape = expected.get("final_shape") or [args.batch_size, 1, args.vocab_size]
    expected_groups = expected.get("groups") or args.groups.split(",")
    expected_processed = expected.get("processed_request_count") or (
        args.microbatch_count * args.batch_size
    )

    baseline_payload = load_json(args.baseline_json)
    candidate_payload = load_json(args.candidate_json) if args.candidate_json.exists() else None
    baseline = summarize_run(args.baseline_json, baseline_payload)
    candidate = summarize_run(args.candidate_json, candidate_payload)

    structural_checks: dict[str, bool] = {
        "candidate_result_exists": candidate_payload is not None,
    }
    if candidate_payload is not None:
        structural_checks.update(
            {
                "verdict_ok": candidate.get("verdict")
                == "ok_dream7b_true_batch_group_major_telemetry",
                "failed_job_count_zero": as_int(candidate.get("failed_job_count")) == 0,
                "microbatch_count_matches": as_int(candidate.get("microbatch_count"))
                == as_int(expected.get("microbatch_count") or args.microbatch_count),
                "processed_request_count_matches": as_int(candidate.get("processed_request_count"))
                == as_int(expected_processed),
                "inner_order_matches": candidate.get("inner_order") == "segment-major",
                "group_ranges_match": candidate.get("group_ranges") == expected_groups,
                "final_logits_mode_last_token": candidate.get("final_logits_mode") == "last-token",
                "final_shape_matches": candidate.get("final_shape") == expected_shape,
                "expected_final_shape_matches": candidate.get("expected_final_shape")
                == expected_shape,
                "preview_shapes_match": all_shapes_match(
                    candidate.get("final_preview_output_shapes") or [],
                    expected_shape,
                ),
            }
        )

    deltas: dict[str, float | None] = {}
    if candidate_payload is not None:
        deltas = {
            "ms_per_request_delta": metric_delta(
                candidate, baseline, "ms_per_request"
            ),
            "avg_bpu_loading_delta": metric_delta(
                candidate, baseline, "avg_bpu_loading"
            ),
            "avg_nonzero_bpu_loading_delta": metric_delta(
                candidate, baseline, "avg_nonzero_bpu_loading"
            ),
            "final_avg_run_ms_delta": metric_delta(
                candidate, baseline, "final_avg_run_ms"
            ),
            "final_run_ms_per_request_delta": metric_delta(
                candidate, baseline, "final_run_ms_per_request"
            ),
        }
        deltas = {key: round_or_none(value, 6) for key, value in deltas.items()}

    structural_ok = all(structural_checks.values())
    performance_checks = {
        "wall_improves_at_least_threshold_ms_per_request": (
            deltas.get("ms_per_request_delta") is not None
            and deltas["ms_per_request_delta"] <= -args.min_wall_improvement_ms_per_request
        ),
        "final_run_improves_at_least_threshold_ms_per_request": (
            deltas.get("final_run_ms_per_request_delta") is not None
            and deltas["final_run_ms_per_request_delta"]
            <= -args.min_final_run_improvement_ms_per_request
        ),
        "nonzero_bpu_not_regressed_past_tolerance": (
            deltas.get("avg_nonzero_bpu_loading_delta") is not None
            and deltas["avg_nonzero_bpu_loading_delta"] >= -args.max_nonzero_bpu_regression_points
        ),
    }
    performance_ok = structural_ok and all(performance_checks.values())

    if candidate_payload is None:
        verdict = "blocked_dream7b_b4_last_token_validation_compare_missing_result"
        decision = "await_last_token_runtime_result"
    elif not structural_ok:
        verdict = "failed_dream7b_b4_last_token_validation_compare_structural_gate"
        decision = "do_not_continue_until_shape_and_runtime_gates_pass"
    elif performance_ok:
        verdict = "ok_dream7b_b4_last_token_validation_compare_continue_runtime_validation"
        decision = "continue_to_longer_or_repeated_validation_before_any_promotion"
    else:
        verdict = "warning_dream7b_b4_last_token_validation_compare_no_clear_runtime_win"
        decision = "do_not_expand_runtime_sweeps_without_a_clear_last_token_win"

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "source_paths": {
            "candidate": str(args.candidate_json),
            "baseline": str(args.baseline_json),
            "runtime_validation_plan": str(args.plan_json),
        },
        "baseline": baseline,
        "candidate": candidate,
        "expected": {
            "final_shape": expected_shape,
            "microbatch_count": expected.get("microbatch_count") or args.microbatch_count,
            "processed_request_count": expected_processed,
            "group_ranges": expected_groups,
            "inner_order": "segment-major",
            "final_logits_mode": "last-token",
        },
        "deltas_candidate_minus_baseline": deltas,
        "structural_checks": structural_checks,
        "performance_checks": performance_checks,
        "decision": {
            "decision": decision,
            "structural_ok": structural_ok,
            "performance_ok": performance_ok,
            "do_not_promote_to_default": True,
            "compare_against": "mb512_segment_major_gap_fields_full_final_collect_baseline",
            "next_if_ok": "repeat_or_extend_validation_only_after queue_batch remains healthy",
        },
        "thresholds": {
            "min_wall_improvement_ms_per_request": args.min_wall_improvement_ms_per_request,
            "min_final_run_improvement_ms_per_request": args.min_final_run_improvement_ms_per_request,
            "max_nonzero_bpu_regression_points": args.max_nonzero_bpu_regression_points,
        },
    }


def render_md(path: Path, payload: dict[str, Any]) -> None:
    decision = payload["decision"]
    lines = [
        "# Dream7B B4 Last-Token Validation Compare",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- decision: `{decision['decision']}`",
        f"- structural_ok: `{decision['structural_ok']}`",
        f"- performance_ok: `{decision['performance_ok']}`",
        f"- compare_against: `{decision['compare_against']}`",
        f"- do_not_promote_to_default: `{decision['do_not_promote_to_default']}`",
        "",
        "## Expected",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in payload["expected"].items())
    lines.extend(["", "## Baseline", ""])
    for key in [
        "path",
        "verdict",
        "microbatch_count",
        "processed_request_count",
        "group_ranges",
        "final_logits_mode",
        "final_shape",
        "ms_per_request",
        "avg_bpu_loading",
        "avg_nonzero_bpu_loading",
        "final_avg_run_ms",
        "final_run_ms_per_request",
    ]:
        lines.append(f"- {key}: `{payload['baseline'].get(key)}`")
    lines.extend(["", "## Candidate", ""])
    for key in [
        "path",
        "exists",
        "verdict",
        "microbatch_count",
        "processed_request_count",
        "failed_job_count",
        "group_ranges",
        "final_logits_mode",
        "final_shape",
        "expected_final_shape",
        "final_preview_output_shapes",
        "ms_per_request",
        "avg_bpu_loading",
        "avg_nonzero_bpu_loading",
        "final_avg_run_ms",
        "final_run_ms_per_request",
    ]:
        lines.append(f"- {key}: `{payload['candidate'].get(key)}`")
    lines.extend(["", "## Deltas Candidate Minus Baseline", ""])
    if payload["deltas_candidate_minus_baseline"]:
        lines.extend(
            f"- {key}: `{value}`"
            for key, value in payload["deltas_candidate_minus_baseline"].items()
        )
    else:
        lines.append("- unavailable: `candidate result is missing`")
    lines.extend(["", "## Structural Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["structural_checks"].items())
    lines.extend(["", "## Performance Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["performance_checks"].items())
    lines.extend(["", "## Thresholds", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["thresholds"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare a future B4 last-token final-logits validation run against the mb512 full-final baseline."
    )
    parser.add_argument("--candidate-json", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--baseline-json", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--plan-json", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--groups", default="0:6,6:12,12:18,18:24,24:28")
    parser.add_argument("--microbatch-count", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--min-wall-improvement-ms-per-request", type=float, default=1.0)
    parser.add_argument("--min-final-run-improvement-ms-per-request", type=float, default=1.0)
    parser.add_argument("--max-nonzero-bpu-regression-points", type=float, default=0.5)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_md(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
