#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_QUEUE_BASELINE_JSON = Path(
    "tmp/b4_runtime_schedule_analysis_20260619/"
    "dream7b_bpu_segment_major_phase_timing_20260614-005702__phase_timing_probe.json"
)


def load_json(path: Path) -> dict[str, Any]:
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


def segment_class(index: int) -> str:
    if index == 0:
        return "token_embedding"
    if index == 27:
        return "final_logits"
    return "hidden_block"


def group_label(group: dict[str, Any]) -> str:
    return f"{group.get('group_start')}:{group.get('group_end')}"


def iter_segment_rows(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in groups:
        label = group_label(group)
        for row in group.get("segment_rows", []) or []:
            copied = dict(row)
            copied["group"] = label
            rows.append(copied)
    return rows


def summarize_classes(segment_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    class_rows: dict[str, list[dict[str, Any]]] = {
        "token_embedding": [],
        "hidden_block": [],
        "final_logits": [],
    }
    for row in segment_rows:
        class_rows[segment_class(as_int(row.get("index")))].append(row)

    summary: dict[str, dict[str, Any]] = {}
    for name, rows in class_rows.items():
        avg_values = [as_float(row.get("avg_run_ms")) for row in rows if row.get("avg_run_ms") is not None]
        completed_values = [as_int(row.get("completed_microbatch_count")) for row in rows]
        summary[name] = {
            "segment_count": len(rows),
            "mean_avg_run_ms": round_or_none(sum(avg_values) / len(avg_values), 4) if avg_values else None,
            "total_run_ms": round(sum(as_float(row.get("total_run_ms")) for row in rows), 3),
            "total_segment_ms": round(sum(as_float(row.get("segment_total_ms")) for row in rows), 3),
            "completed_microbatch_count_min": min(completed_values) if completed_values else None,
            "completed_microbatch_count_max": max(completed_values) if completed_values else None,
        }
    return summary


def analyze_true_batch(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    groups: list[dict[str, Any]] = payload.get("group_rows", []) or []
    requested_groups: list[dict[str, Any]] = payload.get("groups", []) or []
    segment_rows = iter_segment_rows(groups)
    timing_summary = payload.get("timing_summary") or {}

    wall_ms = as_float(payload.get("wall_ms"))
    processed = as_int(payload.get("processed_request_count"))
    microbatches = as_int(payload.get("microbatch_count"))
    batch_size = as_int(payload.get("batch_size"))
    avg_bpu = as_float(payload.get("avg_bpu_loading"))
    nonzero_bpu = as_float(payload.get("avg_nonzero_bpu_loading"))
    group_load_ms = sum(as_float(group.get("group_load_ms")) for group in groups)
    group_release_ms = sum(as_float(group.get("group_release_ms")) for group in groups)

    segment_total_ms = sum(as_float(row.get("segment_total_ms")) for row in segment_rows)
    runtime_run_ms = sum(as_float(row.get("total_run_ms")) for row in segment_rows)
    group_item_ms = sum(as_float(group.get("total_item_ms")) for group in groups)
    measured_active_ms = segment_total_ms or group_item_ms
    measured_run_ms = runtime_run_ms or as_float(timing_summary.get("total_segment_run_ms"))
    estimated_host_gap_ms = wall_ms - group_load_ms - measured_active_ms
    if timing_summary.get("estimated_host_gap_ms") is not None:
        estimated_host_gap_ms = as_float(timing_summary.get("estimated_host_gap_ms"))
    estimated_unaccounted_gap_ms = wall_ms - group_load_ms - measured_active_ms - group_release_ms
    if timing_summary.get("estimated_unaccounted_gap_ms") is not None:
        estimated_unaccounted_gap_ms = as_float(timing_summary.get("estimated_unaccounted_gap_ms"))

    zero_fraction_estimate = 1.0 - (avg_bpu / nonzero_bpu) if nonzero_bpu > 0 else None
    required_nonzero_for_93 = (
        93.0 / max(1e-9, 1.0 - zero_fraction_estimate)
        if zero_fraction_estimate is not None
        else None
    )

    class_summary = summarize_classes(segment_rows)
    hidden_avg = class_summary["hidden_block"]["mean_avg_run_ms"]
    final_avg = class_summary["final_logits"]["mean_avg_run_ms"]

    slowest_segments = sorted(
        [
            {
                "group": row.get("group"),
                "index": as_int(row.get("index")),
                "kind": segment_class(as_int(row.get("index"))),
                "avg_run_ms": round(as_float(row.get("avg_run_ms")), 4),
                "segment_total_ms": round(as_float(row.get("segment_total_ms")), 3),
                "total_run_ms": round(as_float(row.get("total_run_ms")), 3),
                "completed_microbatch_count": as_int(row.get("completed_microbatch_count")),
            }
            for row in segment_rows
        ],
        key=lambda row: (row["avg_run_ms"], row["segment_total_ms"]),
        reverse=True,
    )[:10]

    return {
        "file": str(path),
        "name": path.stem,
        "generated_at": payload.get("generated_at"),
        "verdict": payload.get("verdict"),
        "runtime_version": payload.get("runtime_version"),
        "inner_order": payload.get("inner_order") or "unknown",
        "preallocate_hidden": bool(payload.get("preallocate_hidden", False)),
        "prewarm_hbm": bool(payload.get("prewarm_hbm", False)),
        "release_gc_mode": payload.get("release_gc_mode") or "collect",
        "batch_size": batch_size,
        "microbatch_count": microbatches,
        "processed_request_count": processed,
        "failed_job_count": payload.get("failed_job_count"),
        "group_count": len(groups) if groups else len(requested_groups),
        "completed_group_count": len(groups),
        "group_ranges": [group_label(group) for group in groups]
        or [f"{group.get('start')}:{group.get('end')}" for group in requested_groups],
        "final_shape": payload.get("final_shape"),
        "errors": payload.get("errors") or [],
        "wall_ms": round(wall_ms, 3),
        "amortized_wall_ms_per_request": payload.get("amortized_wall_ms_per_request"),
        "avg_bpu_loading": payload.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": payload.get("avg_nonzero_bpu_loading"),
        "max_bpu_loading": payload.get("max_bpu_loading"),
        "bpu_loading_sample_count": payload.get("bpu_loading_sample_count"),
        "nonzero_bpu_loading_sample_count": payload.get("nonzero_bpu_loading_sample_count"),
        "estimated_zero_fraction_from_bpu": round_or_none(zero_fraction_estimate, 6),
        "required_nonzero_bpu_for_93_avg": round_or_none(required_nonzero_for_93, 3),
        "group_load_ms": round(group_load_ms, 3),
        "total_hbm_prewarm_ms": timing_summary.get("total_hbm_prewarm_ms"),
        "total_hbm_prewarm_mib": timing_summary.get("total_hbm_prewarm_mib"),
        "group_release_ms": round(group_release_ms, 3) if group_release_ms else None,
        "group_load_fraction_of_wall": round_or_none(group_load_ms / wall_ms if wall_ms else None, 6),
        "group_release_fraction_of_wall": round_or_none(group_release_ms / wall_ms if wall_ms and group_release_ms else None, 6),
        "group_load_ms_per_request": round_or_none(group_load_ms / processed if processed else None, 4),
        "total_hidden_materialize_ms": timing_summary.get("total_hidden_materialize_ms"),
        "hidden_materialize_count": timing_summary.get("hidden_materialize_count"),
        "hidden_materialize_ms_per_item": timing_summary.get("hidden_materialize_ms_per_item"),
        "reused_hidden_buffer_count": timing_summary.get("reused_hidden_buffer_count"),
        "segment_total_ms": round(segment_total_ms, 3),
        "group_item_ms": round(group_item_ms, 3),
        "measured_active_ms": round(measured_active_ms, 3),
        "measured_active_fraction_of_wall": round_or_none(measured_active_ms / wall_ms if wall_ms else None, 6),
        "runtime_run_ms": round(measured_run_ms, 3),
        "runtime_run_ms_per_microbatch": round_or_none(measured_run_ms / microbatches if microbatches else None, 4),
        "estimated_host_gap_ms": round(estimated_host_gap_ms, 3),
        "estimated_host_gap_fraction_of_wall": round_or_none(estimated_host_gap_ms / wall_ms if wall_ms else None, 6),
        "estimated_unaccounted_gap_ms": round(estimated_unaccounted_gap_ms, 3),
        "estimated_unaccounted_gap_fraction_of_wall": round_or_none(
            estimated_unaccounted_gap_ms / wall_ms if wall_ms else None, 6
        ),
        "class_summary": class_summary,
        "final_vs_hidden_avg_run_ratio": round_or_none(final_avg / hidden_avg if hidden_avg and final_avg else None, 4),
        "slowest_segments": slowest_segments,
    }


def analyze_queue(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    return {
        "file": str(path),
        "verdict": payload.get("verdict"),
        "processed_request_count": payload.get("processed_request_count"),
        "failed_job_count": payload.get("failed_job_count"),
        "wall_ms": payload.get("wall_ms"),
        "run_ms": payload.get("run_ms"),
        "total_load_ms": payload.get("total_load_ms"),
        "load_to_run_ratio": payload.get("load_to_run_ratio"),
        "amortized_wall_ms_per_processed_request": payload.get("amortized_wall_ms_per_processed_request"),
        "avg_bpu_loading": payload.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": payload.get("avg_nonzero_bpu_loading"),
        "max_bpu_loading": payload.get("max_bpu_loading"),
        "bpu_loading_sample_count": payload.get("bpu_loading_sample_count"),
        "nonzero_bpu_loading_sample_count": payload.get("nonzero_bpu_loading_sample_count"),
    }


def indexed(rows: list[dict[str, Any]]) -> dict[tuple[str, int, int], dict[str, Any]]:
    return {
        (row["inner_order"], row["group_count"], row["microbatch_count"]): row
        for row in rows
    }


def group_signature(row: dict[str, Any]) -> str:
    return ",".join(str(item) for item in row.get("group_ranges") or [])


def find_run(
    rows: list[dict[str, Any]],
    *,
    inner_order: str,
    microbatch_count: int,
    group_ranges: list[str] | None = None,
    group_count: int | None = None,
    release_gc_mode: str | None = None,
    prewarm_hbm: bool | None = None,
) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for row in rows:
        if row.get("inner_order") != inner_order:
            continue
        if as_int(row.get("microbatch_count")) != microbatch_count:
            continue
        if group_ranges is not None and row.get("group_ranges") != group_ranges:
            continue
        if group_count is not None and as_int(row.get("group_count")) != group_count:
            continue
        if release_gc_mode is not None and row.get("release_gc_mode") != release_gc_mode:
            continue
        if prewarm_hbm is not None and bool(row.get("prewarm_hbm")) != prewarm_hbm:
            continue
        matches.append(row)
    if not matches:
        return None
    return max(matches, key=lambda row: str(row.get("generated_at") or ""))


def delta(left: dict[str, Any], right: dict[str, Any], key: str, digits: int = 3) -> float:
    return round(as_float(left.get(key)) - as_float(right.get(key)), digits)


def ratio(left: dict[str, Any], right: dict[str, Any], key: str, digits: int = 4) -> float | None:
    denominator = as_float(right.get(key))
    if denominator == 0.0:
        return None
    return round(as_float(left.get(key)) / denominator, digits)


def build_comparisons(rows: list[dict[str, Any]], queue: dict[str, Any] | None) -> dict[str, Any]:
    rows = [
        row
        for row in rows
        if row.get("verdict") == "ok_dream7b_true_batch_group_major_telemetry"
        and as_int(row.get("processed_request_count")) > 0
    ]
    default_release_rows = [
        row
        for row in rows
        if row.get("release_gc_mode") == "collect"
        and not row.get("prewarm_hbm")
    ]
    comparisons: dict[str, Any] = {}

    default_5_group = ["0:6", "6:12", "12:18", "18:24", "24:28"]
    even_6_group = ["0:5", "5:10", "10:15", "15:20", "20:24", "24:28"]
    final_isolated_6_group = ["0:6", "6:12", "12:18", "18:24", "24:27", "27:28"]

    segment_512 = find_run(
        default_release_rows,
        inner_order="segment-major",
        microbatch_count=512,
        group_ranges=default_5_group,
    )
    micro_512 = find_run(
        default_release_rows,
        inner_order="microbatch-major",
        microbatch_count=512,
        group_ranges=default_5_group,
    )
    if segment_512 and micro_512:
        comparisons["inner_order_mb512_5_groups"] = {
            "segment_major_ms_per_request_delta": delta(
                segment_512, micro_512, "amortized_wall_ms_per_request"
            ),
            "segment_major_avg_bpu_delta": delta(segment_512, micro_512, "avg_bpu_loading"),
            "segment_major_nonzero_bpu_delta": delta(segment_512, micro_512, "avg_nonzero_bpu_loading"),
            "segment_major_load_fraction_delta": delta(
                segment_512, micro_512, "group_load_fraction_of_wall", 6
            ),
        }

    segment_512_g6_even = find_run(
        default_release_rows,
        inner_order="segment-major",
        microbatch_count=512,
        group_ranges=even_6_group,
    )
    segment_512_g6_final = find_run(
        default_release_rows,
        inner_order="segment-major",
        microbatch_count=512,
        group_ranges=final_isolated_6_group,
    )
    segment_512_g7 = find_run(
        default_release_rows,
        inner_order="segment-major",
        microbatch_count=512,
        group_count=7,
    )
    if segment_512 and (segment_512_g6_even or segment_512_g6_final or segment_512_g7):
        comparisons["group_split_mb512_segment_major"] = {
            "five_group_file": segment_512.get("file"),
            "five_group_signature": group_signature(segment_512),
        }
        if segment_512_g6_even:
            comparisons["group_split_mb512_segment_major"].update(
                {
                    "six_group_file": segment_512_g6_even.get("file"),
                    "six_group_signature": group_signature(segment_512_g6_even),
                    "six_group_ms_per_request_delta": delta(
                        segment_512_g6_even, segment_512, "amortized_wall_ms_per_request"
                    ),
                    "six_group_avg_bpu_delta": delta(segment_512_g6_even, segment_512, "avg_bpu_loading"),
                    "six_group_nonzero_bpu_delta": delta(
                        segment_512_g6_even, segment_512, "avg_nonzero_bpu_loading"
                    ),
                    "six_group_load_fraction_delta": delta(
                        segment_512_g6_even, segment_512, "group_load_fraction_of_wall", 6
                    ),
                    "six_group_unaccounted_gap_delta": delta(
                        segment_512_g6_even, segment_512, "estimated_unaccounted_gap_ms"
                    ),
                }
            )
        if segment_512_g6_final:
            comparisons["group_split_mb512_segment_major"].update(
                {
                    "final_isolated_group_file": segment_512_g6_final.get("file"),
                    "final_isolated_group_signature": group_signature(segment_512_g6_final),
                    "final_isolated_group_ms_per_request_delta": delta(
                        segment_512_g6_final, segment_512, "amortized_wall_ms_per_request"
                    ),
                    "final_isolated_group_avg_bpu_delta": delta(
                        segment_512_g6_final, segment_512, "avg_bpu_loading"
                    ),
                    "final_isolated_group_nonzero_bpu_delta": delta(
                        segment_512_g6_final, segment_512, "avg_nonzero_bpu_loading"
                    ),
                    "final_isolated_group_load_fraction_delta": delta(
                        segment_512_g6_final, segment_512, "group_load_fraction_of_wall", 6
                    ),
                    "final_isolated_group_unaccounted_gap_delta": delta(
                        segment_512_g6_final, segment_512, "estimated_unaccounted_gap_ms"
                    ),
                }
            )
        if segment_512_g7:
            comparisons["group_split_mb512_segment_major"].update(
                {
                    "seven_group_file": segment_512_g7.get("file"),
                    "seven_group_signature": group_signature(segment_512_g7),
                    "seven_group_ms_per_request_delta": delta(
                        segment_512_g7, segment_512, "amortized_wall_ms_per_request"
                    ),
                    "seven_group_avg_bpu_delta": delta(segment_512_g7, segment_512, "avg_bpu_loading"),
                    "seven_group_nonzero_bpu_delta": delta(
                        segment_512_g7, segment_512, "avg_nonzero_bpu_loading"
                    ),
                    "seven_group_load_fraction_delta": delta(
                        segment_512_g7, segment_512, "group_load_fraction_of_wall", 6
                    ),
                }
            )

    scaling_candidates = [
        row
        for row in default_release_rows
        if row["inner_order"] == "segment-major"
        and row["group_count"] == 5
        and not row.get("preallocate_hidden")
    ]
    scaling_by_microbatch: dict[int, dict[str, Any]] = {}
    for row in sorted(scaling_candidates, key=lambda item: str(item.get("generated_at") or "")):
        scaling_by_microbatch[row["microbatch_count"]] = row
    scaling = [scaling_by_microbatch[key] for key in sorted(scaling_by_microbatch)]
    comparisons["segment_major_5_group_scaling"] = [
        {
            "microbatch_count": row["microbatch_count"],
            "processed_request_count": row["processed_request_count"],
            "avg_bpu_loading": row["avg_bpu_loading"],
            "avg_nonzero_bpu_loading": row["avg_nonzero_bpu_loading"],
            "ms_per_request": row["amortized_wall_ms_per_request"],
            "group_load_fraction_of_wall": row["group_load_fraction_of_wall"],
            "estimated_zero_fraction_from_bpu": row["estimated_zero_fraction_from_bpu"],
            "required_nonzero_bpu_for_93_avg": row["required_nonzero_bpu_for_93_avg"],
        }
        for row in scaling
    ]
    if scaling:
        first = scaling[0]
        last = scaling[-1]
        comparisons["segment_major_5_group_scaling_delta"] = {
            "microbatch_count_from_to": [first["microbatch_count"], last["microbatch_count"]],
            "avg_bpu_delta": delta(last, first, "avg_bpu_loading"),
            "nonzero_bpu_delta": delta(last, first, "avg_nonzero_bpu_loading"),
            "ms_per_request_ratio": ratio(last, first, "amortized_wall_ms_per_request"),
            "load_fraction_ratio": ratio(last, first, "group_load_fraction_of_wall"),
        }

    for microbatch_count in (128, 512):
        release_collect = find_run(
            default_release_rows,
            inner_order="segment-major",
            microbatch_count=microbatch_count,
            group_ranges=default_5_group,
        )
        release_skip = find_run(
            rows,
            inner_order="segment-major",
            microbatch_count=microbatch_count,
            group_ranges=default_5_group,
            release_gc_mode="skip",
        )
        if release_collect and release_skip:
            comparisons[f"release_gc_mb{microbatch_count}_5_groups"] = {
                "collect_file": release_collect.get("file"),
                "skip_file": release_skip.get("file"),
                "skip_ms_per_request_delta": delta(
                    release_skip, release_collect, "amortized_wall_ms_per_request"
                ),
                "skip_avg_bpu_delta": delta(release_skip, release_collect, "avg_bpu_loading"),
                "skip_nonzero_bpu_delta": delta(
                    release_skip, release_collect, "avg_nonzero_bpu_loading"
                ),
                "skip_total_group_release_ms_delta": delta(
                    release_skip, release_collect, "group_release_ms"
                ),
                "skip_unaccounted_gap_ms_delta": delta(
                    release_skip, release_collect, "estimated_unaccounted_gap_ms"
                ),
            }

    prewarm_128 = find_run(
        rows,
        inner_order="segment-major",
        microbatch_count=128,
        group_ranges=default_5_group,
        release_gc_mode="collect",
        prewarm_hbm=False,
    )
    prewarm_candidates = [
        row
        for row in rows
        if row.get("inner_order") == "segment-major"
        and row.get("microbatch_count") == 128
        and row.get("group_ranges") == default_5_group
        and row.get("release_gc_mode") == "collect"
        and row.get("prewarm_hbm")
    ]
    prewarm_skip_128 = max(prewarm_candidates, key=lambda row: str(row.get("generated_at") or ""), default=None)
    if prewarm_128 and prewarm_skip_128:
        comparisons["prewarm_hbm_mb128_5_groups"] = {
            "baseline_file": prewarm_128.get("file"),
            "prewarm_file": prewarm_skip_128.get("file"),
            "prewarm_wall_ms_per_request_delta": delta(
                prewarm_skip_128, prewarm_128, "amortized_wall_ms_per_request"
            ),
            "prewarm_group_load_ms_delta": delta(
                prewarm_skip_128, prewarm_128, "group_load_ms"
            ),
            "prewarm_group_load_ms_per_request_delta": delta(
                prewarm_skip_128, prewarm_128, "group_load_ms_per_request", 6
            ),
            "prewarm_total_hbm_prewarm_ms": prewarm_skip_128.get("total_hbm_prewarm_ms"),
            "prewarm_total_hbm_prewarm_mib": prewarm_skip_128.get("total_hbm_prewarm_mib"),
            "prewarm_avg_bpu_delta": delta(prewarm_skip_128, prewarm_128, "avg_bpu_loading"),
            "prewarm_nonzero_bpu_delta": delta(prewarm_skip_128, prewarm_128, "avg_nonzero_bpu_loading"),
        }

    latest = max(default_release_rows, key=lambda row: row["microbatch_count"]) if default_release_rows else None
    if latest and queue:
        comparisons["latest_b4_vs_queue_baseline"] = {
            "latest_b4_file": latest["file"],
            "latest_b4_microbatch_count": latest["microbatch_count"],
            "avg_bpu_gap_points": round(
                as_float(latest.get("avg_bpu_loading")) - as_float(queue.get("avg_bpu_loading")), 3
            ),
            "nonzero_bpu_gap_points": round(
                as_float(latest.get("avg_nonzero_bpu_loading"))
                - as_float(queue.get("avg_nonzero_bpu_loading")),
                3,
            ),
            "ms_per_request_ratio_vs_queue": round(
                as_float(latest.get("amortized_wall_ms_per_request"))
                / as_float(queue.get("amortized_wall_ms_per_processed_request")),
                4,
            )
            if as_float(queue.get("amortized_wall_ms_per_processed_request"))
            else None,
        }

    return comparisons


def build_asymptotic(rows: list[dict[str, Any]]) -> dict[str, Any]:
    segment_rows = [
        row
        for row in rows
        if row["inner_order"] == "segment-major"
        and row["group_count"] == 5
        and not row.get("preallocate_hidden")
        and row.get("release_gc_mode") == "collect"
        and row.get("verdict") == "ok_dream7b_true_batch_group_major_telemetry"
        and as_int(row.get("processed_request_count")) > 0
    ]
    segment_rows.sort(key=lambda row: row["microbatch_count"])
    if not segment_rows:
        return {}
    latest = segment_rows[-1]
    fixed_load_ms = as_float(latest.get("group_load_ms"))
    run_ms_per_microbatch = as_float(latest.get("runtime_run_ms_per_microbatch"))
    nonzero_bpu = as_float(latest.get("avg_nonzero_bpu_loading"))
    scenarios = []
    for microbatch_count in [512, 1536, 3072, 6144, 8192, 12288]:
        active_ms = run_ms_per_microbatch * microbatch_count
        wall_ms = fixed_load_ms + active_ms
        load_fraction = fixed_load_ms / wall_ms if wall_ms else 0.0
        scenarios.append(
            {
                "microbatch_count": microbatch_count,
                "processed_request_count": microbatch_count * latest["batch_size"],
                "load_fraction_if_only_load_plus_runtime_run": round(load_fraction, 6),
                "avg_bpu_if_nonzero_stays_latest": round(nonzero_bpu * (1.0 - load_fraction), 3),
                "ms_per_request_if_only_load_plus_runtime_run": round(
                    wall_ms / (microbatch_count * latest["batch_size"]), 4
                ),
            }
        )

    required_nonzero_at_low_load = 93.0 / max(1e-9, 1.0 - 0.05)
    return {
        "source_latest": latest["file"],
        "latest_nonzero_bpu": latest["avg_nonzero_bpu_loading"],
        "latest_runtime_run_ms_per_microbatch": latest["runtime_run_ms_per_microbatch"],
        "latest_group_load_ms": latest["group_load_ms"],
        "required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction": round(
            required_nonzero_at_low_load, 3
        ),
        "note": (
            "Even after fixed-load amortization, average BPU cannot reach 93 if active/nonzero "
            "BPU remains near the latest B4 value."
        ),
        "scenarios": scenarios,
    }


def write_markdown(payload: dict[str, Any], out_md: Path) -> None:
    rows: list[dict[str, Any]] = payload["b4_true_batch_runs"]
    comparisons = payload["comparisons"]
    queue = payload.get("queue_baseline")

    lines = [
        "# Dream7B B4 True-Batch Schedule Analysis",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- telemetry_count: {len(rows)}",
        "",
        "## Run Matrix",
        "",
        "| file | status | order | prealloc | prewarm | release_gc | groups | microbatches | requests | avg_bpu | nonzero_bpu | ms/request | load_share | active_share | host_gap_share |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        ok = row.get("verdict") == "ok_dream7b_true_batch_group_major_telemetry" and as_int(
            row.get("processed_request_count")
        ) > 0
        avg_bpu = row["avg_bpu_loading"] if ok else "n/a"
        nonzero_bpu = row["avg_nonzero_bpu_loading"] if ok else "n/a"
        ms_per_request = row["amortized_wall_ms_per_request"] if ok else "n/a"
        load_share = f"{100 * as_float(row.get('group_load_fraction_of_wall')):.2f}%" if ok else "n/a"
        active_share = f"{100 * as_float(row.get('measured_active_fraction_of_wall')):.2f}%" if ok else "n/a"
        host_gap_share = (
            f"{100 * as_float(row.get('estimated_unaccounted_gap_fraction_of_wall') or row.get('estimated_host_gap_fraction_of_wall')):.2f}%"
            if ok
            else "n/a"
        )
        lines.append(
            f"| {Path(row['file']).name} | {'ok' if ok else 'failed'} | {row['inner_order']} | {row['preallocate_hidden']} | {row['prewarm_hbm']} | {row['release_gc_mode']} | {row['group_count']} | "
            f"{row['microbatch_count']} | {row['processed_request_count']} | "
            f"{avg_bpu} | {nonzero_bpu} | {ms_per_request} | "
            f"{load_share} | {active_share} | {host_gap_share} |"
        )

    lines.extend(["", "## Segment Breakdown", ""])
    latest_segment = max(
        [
            row
            for row in rows
            if row["inner_order"] == "segment-major"
            and row.get("verdict") == "ok_dream7b_true_batch_group_major_telemetry"
            and as_int(row.get("processed_request_count")) > 0
        ],
        key=lambda row: row["microbatch_count"],
    )
    class_summary = latest_segment["class_summary"]
    lines.extend(
        [
            f"- latest_segment_major_file: {Path(latest_segment['file']).name}",
            f"- token_embedding_avg_run_ms: {class_summary['token_embedding']['mean_avg_run_ms']}",
            f"- hidden_block_avg_run_ms: {class_summary['hidden_block']['mean_avg_run_ms']}",
            f"- final_logits_avg_run_ms: {class_summary['final_logits']['mean_avg_run_ms']}",
            f"- final_vs_hidden_avg_run_ratio: {latest_segment['final_vs_hidden_avg_run_ratio']}",
            "",
            "| rank | group | segment | kind | avg_run_ms | completed_microbatches |",
            "| ---: | --- | ---: | --- | ---: | ---: |",
        ]
    )
    for rank, row in enumerate(latest_segment["slowest_segments"][:8], start=1):
        lines.append(
            f"| {rank} | {row['group']} | {row['index']} | {row['kind']} | "
            f"{row['avg_run_ms']} | {row['completed_microbatch_count']} |"
        )

    lines.extend(["", "## Scheduling Comparisons", ""])
    inner = comparisons.get("inner_order_mb512_5_groups")
    if inner:
        lines.extend(
            [
                "- 512 microbatch inner-order test, 5 groups:",
                f"  - segment-major ms/request delta: {inner['segment_major_ms_per_request_delta']}",
                f"  - segment-major avg BPU delta: {inner['segment_major_avg_bpu_delta']} points",
                f"  - segment-major nonzero BPU delta: {inner['segment_major_nonzero_bpu_delta']} points",
                f"  - load-share delta: {inner['segment_major_load_fraction_delta']}",
            ]
        )
    split = comparisons.get("group_split_mb512_segment_major")
    if split:
        lines.extend(
            [
                "- 512 microbatch group split test, segment-major:",
            ]
        )
        if "six_group_ms_per_request_delta" in split:
            lines.extend(
                [
                    f"  - 6-group even signature: {split.get('six_group_signature')}",
                    f"  - 6-group even ms/request delta vs 5-group: {split['six_group_ms_per_request_delta']}",
                    f"  - 6-group avg BPU delta vs 5-group: {split['six_group_avg_bpu_delta']} points",
                    f"  - 6-group nonzero BPU delta vs 5-group: {split['six_group_nonzero_bpu_delta']} points",
                    f"  - 6-group load-share delta vs 5-group: {split['six_group_load_fraction_delta']}",
                    f"  - 6-group unaccounted-gap delta vs 5-group: {split['six_group_unaccounted_gap_delta']} ms",
                ]
            )
        if "final_isolated_group_ms_per_request_delta" in split:
            lines.extend(
                [
                    f"  - final-isolated signature: {split.get('final_isolated_group_signature')}",
                    f"  - final-isolated ms/request delta vs 5-group: {split['final_isolated_group_ms_per_request_delta']}",
                    f"  - final-isolated avg BPU delta vs 5-group: {split['final_isolated_group_avg_bpu_delta']} points",
                    f"  - final-isolated nonzero BPU delta vs 5-group: {split['final_isolated_group_nonzero_bpu_delta']} points",
                    f"  - final-isolated load-share delta vs 5-group: {split['final_isolated_group_load_fraction_delta']}",
                    f"  - final-isolated unaccounted-gap delta vs 5-group: {split['final_isolated_group_unaccounted_gap_delta']} ms",
                ]
            )
        if "seven_group_ms_per_request_delta" in split:
            lines.extend(
                [
                    f"  - 7-group signature: {split.get('seven_group_signature')}",
                    f"  - 7-group ms/request delta vs 5-group: {split['seven_group_ms_per_request_delta']}",
                    f"  - 7-group avg BPU delta vs 5-group: {split['seven_group_avg_bpu_delta']} points",
                    f"  - 7-group nonzero BPU delta vs 5-group: {split['seven_group_nonzero_bpu_delta']} points",
                    f"  - 7-group load-share delta vs 5-group: {split['seven_group_load_fraction_delta']}",
                ]
            )
    for microbatch_count in (128, 512):
        release_gc = comparisons.get(f"release_gc_mb{microbatch_count}_5_groups")
        if release_gc:
            lines.extend(
                [
                    f"- {microbatch_count} microbatch release-GC test, 5 groups:",
                    f"  - skip-GC ms/request delta: {release_gc['skip_ms_per_request_delta']}",
                    f"  - skip-GC avg BPU delta: {release_gc['skip_avg_bpu_delta']} points",
                    f"  - skip-GC nonzero BPU delta: {release_gc['skip_nonzero_bpu_delta']} points",
                    f"  - skip-GC total group-release delta: {release_gc['skip_total_group_release_ms_delta']} ms",
                    f"  - skip-GC unaccounted-gap delta: {release_gc['skip_unaccounted_gap_ms_delta']} ms",
                ]
            )
    prewarm = comparisons.get("prewarm_hbm_mb128_5_groups")
    if prewarm:
        lines.extend(
            [
                "- 128 microbatch HBM prewarm test, 5 groups:",
                f"  - prewarm wall ms/request delta: {prewarm['prewarm_wall_ms_per_request_delta']}",
                f"  - prewarm group-load delta: {prewarm['prewarm_group_load_ms_delta']} ms",
                f"  - prewarm group-load ms/request delta: {prewarm['prewarm_group_load_ms_per_request_delta']}",
                f"  - prewarm read time: {prewarm['prewarm_total_hbm_prewarm_ms']} ms for {prewarm['prewarm_total_hbm_prewarm_mib']} MiB",
                f"  - prewarm avg BPU delta: {prewarm['prewarm_avg_bpu_delta']} points",
                f"  - prewarm nonzero BPU delta: {prewarm['prewarm_nonzero_bpu_delta']} points",
            ]
        )

    lines.extend(
        [
            "",
            "## Long-Queue Scaling",
            "",
            "| microbatches | requests | avg_bpu | nonzero_bpu | ms/request | load_share | required_nonzero_for_93_avg |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in comparisons.get("segment_major_5_group_scaling", []):
        lines.append(
            f"| {row['microbatch_count']} | {row['processed_request_count']} | "
            f"{row['avg_bpu_loading']} | {row['avg_nonzero_bpu_loading']} | "
            f"{row['ms_per_request']} | {100 * as_float(row['group_load_fraction_of_wall']):.2f}% | "
            f"{row['required_nonzero_bpu_for_93_avg']} |"
        )
    scaling_delta = comparisons.get("segment_major_5_group_scaling_delta")
    if scaling_delta:
        from_mb, to_mb = scaling_delta["microbatch_count_from_to"]
        lines.extend(
            [
                "",
                f"- {from_mb} to {to_mb} microbatches raises avg BPU by {scaling_delta['avg_bpu_delta']} points.",
                f"- Nonzero BPU changes by only {scaling_delta['nonzero_bpu_delta']} points.",
                f"- ms/request ratio is {scaling_delta['ms_per_request_ratio']}; load fraction ratio is {scaling_delta['load_fraction_ratio']}.",
            ]
        )

    if queue:
        latest_gap = comparisons.get("latest_b4_vs_queue_baseline", {})
        lines.extend(
            [
                "",
                "## Queue Baseline",
                "",
                f"- queue_baseline_status: {payload.get('queue_baseline_status')}",
                f"- queue_baseline_path: {payload.get('queue_baseline_path')}",
                f"- queue_avg_bpu: {queue.get('avg_bpu_loading')}",
                f"- queue_nonzero_bpu: {queue.get('avg_nonzero_bpu_loading')}",
                f"- queue_ms_per_request: {queue.get('amortized_wall_ms_per_processed_request')}",
                f"- latest_b4_avg_bpu_gap_points: {latest_gap.get('avg_bpu_gap_points')}",
                f"- latest_b4_nonzero_bpu_gap_points: {latest_gap.get('nonzero_bpu_gap_points')}",
                f"- latest_b4_ms_per_request_ratio_vs_queue: {latest_gap.get('ms_per_request_ratio_vs_queue')}",
            ]
        )

    failed_rows = [row for row in rows if row.get("verdict") != "ok_dream7b_true_batch_group_major_telemetry"]
    if failed_rows:
        lines.extend(
            [
                "",
                "## Failed Capacity Probes",
                "",
                "| file | order | groups | group_ranges | error |",
                "| --- | --- | ---: | --- | --- |",
            ]
        )
        for row in failed_rows:
            lines.append(
                f"| {Path(row['file']).name} | {row['inner_order']} | {row['group_count']} | "
                f"{','.join(row.get('group_ranges') or [])} | {row.get('errors', [''])[0] if row.get('errors') else ''} |"
            )

    asymptotic = payload.get("asymptotic_projection", {})
    lines.extend(
        [
            "",
            "## Asymptotic Projection",
            "",
            f"- source_latest: {Path(asymptotic.get('source_latest', '')).name}",
            f"- latest_nonzero_bpu: {asymptotic.get('latest_nonzero_bpu')}",
            f"- required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction: {asymptotic.get('required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction')}",
            f"- note: {asymptotic.get('note')}",
            "",
            "| microbatches | requests | projected_load_fraction | projected_avg_bpu_if_nonzero_unchanged | projected_ms/request |",
            "| ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in asymptotic.get("scenarios", []):
        lines.append(
            f"| {row['microbatch_count']} | {row['processed_request_count']} | "
            f"{100 * row['load_fraction_if_only_load_plus_runtime_run']:.2f}% | "
            f"{row['avg_bpu_if_nonzero_stays_latest']} | "
            f"{row['ms_per_request_if_only_load_plus_runtime_run']} |"
        )

    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            "- B=4 true-batch HBM is useful as a throughput research artifact, but current active/nonzero BPU remains below the queue baseline.",
            "- More microbatches mainly amortize fixed group load; they do not raise active BPU intensity enough by themselves.",
            "- Segment-major is only a small win over microbatch-major at 512 microbatches.",
            "- Splitting into more groups is not promising for the current 512 microbatch data because it slightly worsens wall time and BPU.",
            "- The final logits segment is the main runtime outlier and should be treated as a separate scheduling target.",
        ]
    )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolve_telemetry_files(args: argparse.Namespace) -> list[Path]:
    files: list[Path] = []
    for item in args.telemetry_json or []:
        files.append(Path(item))
    if args.telemetry_dir:
        files.extend(sorted(Path(args.telemetry_dir).glob(args.telemetry_glob)))
    unique: dict[Path, None] = {}
    for path in files:
        unique[path] = None
    return [path for path in unique if path.is_file()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--telemetry-dir", default="tmp/remote_true_batch_reports")
    parser.add_argument("--telemetry-glob", default="b4_*true_batch_group_major_telemetry.json")
    parser.add_argument("--telemetry-json", action="append")
    parser.add_argument("--queue-baseline-json")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--out-stem", default="dream7b_true_batch_b4_schedule_analysis_current")
    args = parser.parse_args()

    telemetry_files = resolve_telemetry_files(args)
    if not telemetry_files:
        raise SystemExit("no telemetry JSON files found")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = [analyze_true_batch(path) for path in telemetry_files]
    rows.sort(
        key=lambda row: (
            row["batch_size"],
            row["microbatch_count"],
            row["inner_order"],
            row["group_count"],
            row["preallocate_hidden"],
            row["prewarm_hbm"],
            row["release_gc_mode"],
            row["file"],
        )
    )

    queue = None
    queue_baseline_path = Path(args.queue_baseline_json) if args.queue_baseline_json else DEFAULT_QUEUE_BASELINE_JSON
    queue_baseline_status = "missing"
    if queue_baseline_path.is_file():
        queue = analyze_queue(queue_baseline_path)
        queue_baseline_status = "explicit" if args.queue_baseline_json else "default"

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_true_batch_b4_schedule_analysis_current",
        "b4_true_batch_runs": rows,
        "queue_baseline": queue,
        "queue_baseline_path": str(queue_baseline_path),
        "queue_baseline_status": queue_baseline_status,
        "comparisons": build_comparisons(rows, queue),
        "asymptotic_projection": build_asymptotic(rows),
    }

    out_json = out_dir / f"{args.out_stem}.json"
    out_md = out_dir / f"{args.out_stem}.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload, out_md)
    print(out_json)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
