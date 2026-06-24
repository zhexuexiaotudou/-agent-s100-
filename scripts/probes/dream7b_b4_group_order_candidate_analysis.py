#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_OUT_JSON = Path(
    "tmp/b4_runtime_schedule_analysis_20260619/"
    "dream7b_b4_group_order_candidate_analysis_20260620.json"
)
DEFAULT_OUT_MD = Path(
    "tmp/b4_runtime_schedule_analysis_20260619/"
    "dream7b_b4_group_order_candidate_analysis_20260620.md"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def as_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except Exception:
        return 0


def round_or_none(value: float | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def segment_kind(index: int) -> str:
    if index == 0:
        return "token_embedding"
    if index == 27:
        return "final_logits"
    return "hidden_block"


def range_label(start: int, end: int) -> str:
    return f"{start}:{end}"


def parse_range(label: str) -> tuple[int, int]:
    left, right = str(label).split(":", 1)
    return int(left), int(right)


def group_ranges_from_bounds(bounds: list[tuple[int, int]]) -> list[str]:
    return [range_label(start, end) for start, end in bounds]


def is_ok(row: dict[str, Any]) -> bool:
    return row.get("verdict") == "ok_dream7b_true_batch_group_major_telemetry"


def find_run(
    runs: list[dict[str, Any]],
    *,
    microbatch_count: int,
    inner_order: str,
    group_ranges: list[str] | None = None,
    group_count: int | None = None,
    preallocate_hidden: bool | None = False,
) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for row in runs:
        if not is_ok(row):
            continue
        if as_int(row.get("microbatch_count")) != microbatch_count:
            continue
        if row.get("inner_order") != inner_order:
            continue
        if group_ranges is not None and row.get("group_ranges") != group_ranges:
            continue
        if group_count is not None and as_int(row.get("group_count")) != group_count:
            continue
        if preallocate_hidden is not None and bool(row.get("preallocate_hidden")) != preallocate_hidden:
            continue
        matches.append(row)
    if not matches:
        return None
    return min(matches, key=lambda row: as_float(row.get("amortized_wall_ms_per_request")))


def variant_row(label: str, baseline: dict[str, Any], run: dict[str, Any] | None) -> dict[str, Any]:
    if not run:
        return {
            "label": label,
            "status": "missing",
        }
    return {
        "label": label,
        "status": "observed",
        "file": run.get("file"),
        "microbatch_count": run.get("microbatch_count"),
        "inner_order": run.get("inner_order"),
        "group_count": run.get("group_count"),
        "group_ranges": run.get("group_ranges"),
        "ms_per_request": run.get("amortized_wall_ms_per_request"),
        "avg_bpu_loading": run.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": run.get("avg_nonzero_bpu_loading"),
        "delta_ms_per_request_vs_baseline": round_or_none(
            as_float(run.get("amortized_wall_ms_per_request"))
            - as_float(baseline.get("amortized_wall_ms_per_request")),
            3,
        ),
        "delta_avg_bpu_vs_baseline": round_or_none(
            as_float(run.get("avg_bpu_loading")) - as_float(baseline.get("avg_bpu_loading")),
            3,
        ),
        "delta_nonzero_bpu_vs_baseline": round_or_none(
            as_float(run.get("avg_nonzero_bpu_loading"))
            - as_float(baseline.get("avg_nonzero_bpu_loading")),
            3,
        ),
    }


def group_label(group: dict[str, Any]) -> str:
    return range_label(as_int(group.get("group_start")), as_int(group.get("group_end")))


def segment_table(telemetry: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for group in telemetry.get("group_rows") or []:
        loaded_by_index = {
            as_int(item.get("index")): item for item in group.get("loaded_segments") or []
        }
        for segment in group.get("segment_rows") or []:
            index = as_int(segment.get("index"))
            loaded = loaded_by_index.get(index) or {}
            rows[index] = {
                "index": index,
                "kind": segment_kind(index),
                "hbm_size_mib": round(as_float(loaded.get("hbm_size_mib")), 3),
                "load_ms": round(as_float(loaded.get("load_ms")), 3),
                "segment_total_ms": round(as_float(segment.get("segment_total_ms")), 3),
                "total_run_ms": round(as_float(segment.get("total_run_ms")), 3),
                "hidden_materialize_ms": round(as_float(segment.get("hidden_materialize_ms")), 3),
                "inter_segment_first_run_gap_ms": segment.get("inter_segment_first_run_gap_ms"),
                "intra_segment_run_gap_ms": segment.get("intra_segment_run_gap_ms"),
            }
    return rows


def measured_release_ms_by_group_count(telemetry: dict[str, Any]) -> dict[int, float]:
    groups = telemetry.get("group_rows") or []
    release_values = [as_float(group.get("group_release_ms")) for group in groups]
    release_values = [value for value in release_values if value > 0]
    if not release_values:
        return {}
    return {len(groups): sum(release_values) / len(release_values)}


def candidate_from_ranges(
    label: str,
    ranges: list[str],
    segments: dict[int, dict[str, Any]],
    processed_request_count: int,
    release_ms_per_group: float,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    group_rows: list[dict[str, Any]] = []
    total_load_ms = 0.0
    total_release_ms = 0.0
    total_segment_ms = 0.0
    max_group_hbm_mib = 0.0
    max_group_load_ms = 0.0
    for label_range in ranges:
        start, end = parse_range(label_range)
        indexes = list(range(start, end))
        group_hbm_mib = sum(as_float((segments.get(index) or {}).get("hbm_size_mib")) for index in indexes)
        group_load_ms = sum(as_float((segments.get(index) or {}).get("load_ms")) for index in indexes)
        group_segment_ms = sum(
            as_float((segments.get(index) or {}).get("segment_total_ms")) for index in indexes
        )
        contains_final = 27 in indexes
        group_rows.append(
            {
                "group": label_range,
                "loaded_count": len(indexes),
                "contains_final_logits": contains_final,
                "hbm_size_mib": round(group_hbm_mib, 3),
                "load_ms": round(group_load_ms, 3),
                "segment_total_ms": round(group_segment_ms, 3),
                "estimated_release_ms": round(release_ms_per_group, 3),
            }
        )
        total_load_ms += group_load_ms
        total_release_ms += release_ms_per_group
        total_segment_ms += group_segment_ms
        max_group_hbm_mib = max(max_group_hbm_mib, group_hbm_mib)
        max_group_load_ms = max(max_group_load_ms, group_load_ms)

    baseline_group_count = as_int(baseline.get("group_count"))
    baseline_release_total = release_ms_per_group * baseline_group_count
    release_delta = total_release_ms - baseline_release_total
    return {
        "label": label,
        "group_ranges": ranges,
        "group_count": len(ranges),
        "max_group_hbm_mib": round(max_group_hbm_mib, 3),
        "max_group_load_ms": round(max_group_load_ms, 3),
        "estimated_total_load_ms": round(total_load_ms, 3),
        "estimated_total_segment_ms": round(total_segment_ms, 3),
        "estimated_total_release_ms": round(total_release_ms, 3),
        "estimated_release_delta_ms_vs_baseline": round(release_delta, 3),
        "estimated_release_delta_ms_per_request_vs_baseline": round_or_none(
            release_delta / processed_request_count if processed_request_count else None,
            6,
        ),
        "group_rows": group_rows,
    }


def max_hbm_for_ranges(ranges: list[str], segments: dict[int, dict[str, Any]]) -> float:
    max_size = 0.0
    for label in ranges:
        start, end = parse_range(label)
        max_size = max(
            max_size,
            sum(as_float((segments.get(index) or {}).get("hbm_size_mib")) for index in range(start, end)),
        )
    return max_size


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    schedule = read_json(args.schedule_json)
    runs = schedule.get("b4_true_batch_runs") or []
    baseline_ranges = ["0:6", "6:12", "12:18", "18:24", "24:28"]
    baseline = find_run(
        runs,
        microbatch_count=512,
        inner_order="segment-major",
        group_ranges=baseline_ranges,
    )
    if baseline is None:
        raise RuntimeError("mb512 segment-major baseline run not found")

    telemetry = read_json(args.telemetry_json)
    segments = segment_table(telemetry)
    processed = as_int(telemetry.get("processed_request_count"))
    releases = measured_release_ms_by_group_count(telemetry)
    release_ms_per_group = next(iter(releases.values()), 0.0)

    observed_variants = [
        variant_row("mb512_segment_major_5g_baseline", baseline, baseline),
        variant_row(
            "mb512_microbatch_major_same_ranges",
            baseline,
            find_run(
                runs,
                microbatch_count=512,
                inner_order="microbatch-major",
                group_ranges=baseline_ranges,
            ),
        ),
        variant_row(
            "mb512_segment_major_g6_even",
            baseline,
            find_run(
                runs,
                microbatch_count=512,
                inner_order="segment-major",
                group_ranges=["0:5", "5:10", "10:15", "15:20", "20:24", "24:28"],
            ),
        ),
        variant_row(
            "mb512_segment_major_g7_even",
            baseline,
            find_run(
                runs,
                microbatch_count=512,
                inner_order="segment-major",
                group_ranges=["0:4", "4:8", "8:12", "12:16", "16:20", "20:24", "24:28"],
            ),
        ),
        variant_row(
            "mb512_segment_major_final_isolated",
            baseline,
            find_run(
                runs,
                microbatch_count=512,
                inner_order="segment-major",
                group_ranges=["0:6", "6:12", "12:18", "18:24", "24:27", "27:28"],
            ),
        ),
    ]

    candidate_ranges = {
        "current_5g_success_boundary": baseline_ranges,
        "g6_even_lower_peak_hbm": ["0:5", "5:10", "10:15", "15:20", "20:24", "24:28"],
        "g7_even_lower_peak_hbm": ["0:4", "4:8", "8:12", "12:16", "16:20", "20:24", "24:28"],
        "final_logits_isolated": ["0:6", "6:12", "12:18", "18:24", "24:27", "27:28"],
        "failed_g4_reference": ["0:7", "7:14", "14:21", "21:28"],
    }
    candidates = [
        candidate_from_ranges(
            label,
            ranges,
            segments,
            processed,
            release_ms_per_group,
            baseline,
        )
        for label, ranges in candidate_ranges.items()
    ]

    current_peak = max_hbm_for_ranges(baseline_ranges, segments)
    failed_g4_peak = max_hbm_for_ranges(candidate_ranges["failed_g4_reference"], segments)
    for candidate in candidates:
        peak = as_float(candidate.get("max_group_hbm_mib"))
        if candidate["label"] == "failed_g4_reference":
            candidate["capacity_risk"] = "observed_failed_at_mb128"
        elif peak <= current_peak * 1.01:
            candidate["capacity_risk"] = "not_higher_than_observed_mb512_success"
        elif peak >= failed_g4_peak * 0.98:
            candidate["capacity_risk"] = "near_observed_failed_g4_peak"
        else:
            candidate["capacity_risk"] = "between_observed_success_and_failed_peaks"

    successful_variants = [
        row
        for row in observed_variants
        if row.get("status") == "observed" and row["label"] != "mb512_segment_major_5g_baseline"
    ]
    best_nonbaseline_variant = min(
        successful_variants,
        key=lambda row: as_float(row.get("delta_ms_per_request_vs_baseline")),
    )
    microbatch_variant = next(
        row for row in observed_variants if row["label"] == "mb512_microbatch_major_same_ranges"
    )
    largest_candidate_delta = max(
        abs(as_float(row.get("delta_ms_per_request_vs_baseline"))) for row in successful_variants
    )
    decision = {
        "baseline": "mb512_segment_major_5g_baseline",
        "segment_major_preferred_over_microbatch_major": as_float(
            microbatch_variant.get("delta_ms_per_request_vs_baseline")
        )
        > 0,
        "best_nonbaseline_observed_variant": best_nonbaseline_variant.get("label"),
        "best_nonbaseline_observed_variant_delta_ms_per_request": best_nonbaseline_variant.get(
            "delta_ms_per_request_vs_baseline"
        ),
        "no_observed_variant_beats_baseline": as_float(
            best_nonbaseline_variant.get("delta_ms_per_request_vs_baseline")
        )
        >= 0,
        "observed_group_order_variants_within_noise_band": largest_candidate_delta < 1.0,
        "more_mb512_group_boundary_sweeps_deprioritized": True,
        "mb768_or_higher_group_sweeps_blocked_by_capacity_boundary": True,
        "only_capacity_probe_if_needed": "g7_even_lower_peak_hbm",
        "next_runtime_candidate": "final_logits_compute_reduction_or_output_avoidance",
        "reason": (
            "At mb512, microbatch-major, g6, g7, and final-isolated variants are all within "
            "1 ms/request of the segment-major 5-group baseline, while mb768/mb1024 capacity "
            "failures make larger microbatch group sweeps a poor next lever."
        ),
    }
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_group_order_candidate_analysis",
        "source_paths": {
            "schedule": str(args.schedule_json),
            "telemetry": str(args.telemetry_json),
        },
        "baseline": {
            "file": baseline.get("file"),
            "microbatch_count": baseline.get("microbatch_count"),
            "inner_order": baseline.get("inner_order"),
            "group_ranges": baseline.get("group_ranges"),
            "ms_per_request": baseline.get("amortized_wall_ms_per_request"),
            "avg_bpu_loading": baseline.get("avg_bpu_loading"),
            "avg_nonzero_bpu_loading": baseline.get("avg_nonzero_bpu_loading"),
            "max_group_hbm_mib": round(current_peak, 3),
        },
        "observed_variants": observed_variants,
        "candidate_group_shapes": candidates,
        "capacity_reference": {
            "observed_success_peak_group_hbm_mib": round(current_peak, 3),
            "observed_failed_g4_peak_group_hbm_mib": round(failed_g4_peak, 3),
            "mb768_gap_field_failed_at": "seg02_03",
            "mb1024_gap_field_failed_at": "seg10_11",
        },
        "decision": decision,
    }


def render_md(payload: dict[str, Any], out_md: Path) -> None:
    decision = payload["decision"]
    lines = [
        "# Dream7B B4 Group/Order Candidate Analysis",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- baseline: {decision['baseline']}",
        f"- next_runtime_candidate: {decision['next_runtime_candidate']}",
        f"- reason: {decision['reason']}",
        "",
        "## Observed Variants",
        "",
        "| label | order | groups | ms/request | delta ms/request | avg BPU | delta avg BPU |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["observed_variants"]:
        lines.append(
            f"| {row.get('label')} | {row.get('inner_order')} | {row.get('group_count')} | "
            f"{row.get('ms_per_request')} | {row.get('delta_ms_per_request_vs_baseline')} | "
            f"{row.get('avg_bpu_loading')} | {row.get('delta_avg_bpu_vs_baseline')} |"
        )
    lines.extend(
        [
            "",
            "## Candidate Group Shapes",
            "",
            "| label | groups | max HBM MiB | max load ms | release delta ms/request | capacity risk |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["candidate_group_shapes"]:
        lines.append(
            f"| {row.get('label')} | {row.get('group_count')} | {row.get('max_group_hbm_mib')} | "
            f"{row.get('max_group_load_ms')} | "
            f"{row.get('estimated_release_delta_ms_per_request_vs_baseline')} | "
            f"{row.get('capacity_risk')} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- segment_major_preferred_over_microbatch_major: {decision['segment_major_preferred_over_microbatch_major']}",
            f"- best_nonbaseline_observed_variant: {decision['best_nonbaseline_observed_variant']}",
            f"- best_nonbaseline_observed_variant_delta_ms_per_request: {decision['best_nonbaseline_observed_variant_delta_ms_per_request']}",
            f"- no_observed_variant_beats_baseline: {decision['no_observed_variant_beats_baseline']}",
            f"- observed_group_order_variants_within_noise_band: {decision['observed_group_order_variants_within_noise_band']}",
            f"- more_mb512_group_boundary_sweeps_deprioritized: {decision['more_mb512_group_boundary_sweeps_deprioritized']}",
            f"- mb768_or_higher_group_sweeps_blocked_by_capacity_boundary: {decision['mb768_or_higher_group_sweeps_blocked_by_capacity_boundary']}",
            f"- only_capacity_probe_if_needed: {decision['only_capacity_probe_if_needed']}",
            "",
            "## Source Paths",
            "",
        ]
    )
    lines.extend(f"- {key}: {value}" for key, value in payload["source_paths"].items())
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schedule-json",
        type=Path,
        default=Path(
            "tmp/b4_runtime_schedule_analysis_20260619/"
            "dream7b_true_batch_b4_schedule_analysis_current.json"
        ),
    )
    parser.add_argument(
        "--telemetry-json",
        type=Path,
        default=Path(
            "tmp/remote_true_batch_reports/"
            "b4_mb512_segment_major_gap_fields_true_batch_group_major_telemetry.json"
        ),
    )
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_md(payload, args.out_md)
    print(args.out_json)
    print(args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
