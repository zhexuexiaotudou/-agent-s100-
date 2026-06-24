#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_SCHEDULE = DEFAULT_ROOT / "dream7b_true_batch_b4_schedule_analysis_current.json"
DEFAULT_LOAD_TELEMETRY = (
    Path("tmp/remote_true_batch_reports")
    / "b4_mb128_segment_major_load_attributed_true_batch_group_major_telemetry.json"
)
DEFAULT_GROUP_ORDER = DEFAULT_ROOT / "dream7b_b4_group_order_candidate_analysis_20260620.json"
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_group_partition_planner_20260620.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_group_partition_planner_20260620.md"


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
    return round(value, digits) if value is not None else None


def segment_kind(index: int) -> str:
    if index == 0:
        return "token_embedding"
    if index == 27:
        return "final_logits"
    return "hidden_block"


def group_label(group: tuple[int, int]) -> str:
    return f"{group[0]}:{group[1]}"


def parse_label(label: str) -> tuple[int, int]:
    left, right = str(label).split(":", 1)
    return int(left), int(right)


def segment_table(telemetry: dict[str, Any]) -> dict[int, dict[str, Any]]:
    segments: dict[int, dict[str, Any]] = {}
    for group in telemetry.get("group_rows") or []:
        for row in group.get("loaded_segments") or []:
            index = as_int(row.get("index"))
            segments[index] = {
                "index": index,
                "kind": segment_kind(index),
                "hbm_size_mib": as_float(row.get("hbm_size_mib")),
                "load_ms": as_float(row.get("load_ms")),
            }
    return segments


def enumerate_partitions(
    *,
    start: int,
    end: int,
    group_count: int,
    min_group_segments: int,
    max_group_segments: int,
) -> list[list[tuple[int, int]]]:
    result: list[list[tuple[int, int]]] = []

    def visit(position: int, groups_left: int, current: list[tuple[int, int]]) -> None:
        if groups_left == 1:
            size = end - position
            if min_group_segments <= size <= max_group_segments:
                result.append([*current, (position, end)])
            return
        remaining_after = groups_left - 1
        min_next_end = position + min_group_segments
        max_next_end = min(
            position + max_group_segments,
            end - remaining_after * min_group_segments,
        )
        for next_end in range(min_next_end, max_next_end + 1):
            if end - next_end > remaining_after * max_group_segments:
                continue
            visit(next_end, remaining_after, [*current, (position, next_end)])

    visit(start, group_count, [])
    return result


def run_key_from_ranges(ranges: list[str]) -> str:
    return ",".join(ranges)


def observed_variant_map(schedule: dict[str, Any]) -> dict[str, dict[str, Any]]:
    observed: dict[str, dict[str, Any]] = {}
    for row in schedule.get("b4_true_batch_runs") or []:
        if row.get("verdict") != "ok_dream7b_true_batch_group_major_telemetry":
            continue
        if row.get("inner_order") != "segment-major":
            continue
        if as_int(row.get("microbatch_count")) != 512:
            continue
        if bool(row.get("preallocate_hidden")):
            continue
        if bool(row.get("prewarm_hbm")):
            continue
        if row.get("release_gc_mode") != "collect":
            continue
        ranges = row.get("group_ranges") or []
        key = run_key_from_ranges(ranges)
        current = observed.get(key)
        if current is None or as_float(row.get("amortized_wall_ms_per_request")) < as_float(
            current.get("amortized_wall_ms_per_request")
        ):
            observed[key] = row
    return observed


def partition_stats(
    partition: list[tuple[int, int]],
    segments: dict[int, dict[str, Any]],
    baseline_peak_mib: float,
    failed_peak_mib: float,
    observed: dict[str, dict[str, Any]],
    baseline_ms_per_request: float,
    release_ms_per_group: float,
    processed_request_count: int,
) -> dict[str, Any]:
    ranges = [group_label(group) for group in partition]
    group_rows: list[dict[str, Any]] = []
    max_group_hbm_mib = 0.0
    max_group_load_ms = 0.0
    contains_final_singleton = False
    for start, end in partition:
        indexes = list(range(start, end))
        hbm = sum((segments.get(index) or {}).get("hbm_size_mib", 0.0) for index in indexes)
        load = sum((segments.get(index) or {}).get("load_ms", 0.0) for index in indexes)
        max_group_hbm_mib = max(max_group_hbm_mib, hbm)
        max_group_load_ms = max(max_group_load_ms, load)
        contains_final_singleton = contains_final_singleton or (start == 27 and end == 28)
        group_rows.append(
            {
                "group": group_label((start, end)),
                "segments": len(indexes),
                "contains_final_logits": 27 in indexes,
                "hbm_size_mib": round(hbm, 3),
                "load_ms": round(load, 3),
            }
        )
    observed_run = observed.get(run_key_from_ranges(ranges))
    observed_delta = None
    if observed_run:
        observed_delta = round_or_none(
            as_float(observed_run.get("amortized_wall_ms_per_request")) - baseline_ms_per_request,
            3,
        )
    release_delta_ms = release_ms_per_group * (len(partition) - 5)
    peak_delta_pct = (
        (max_group_hbm_mib - baseline_peak_mib) / baseline_peak_mib * 100.0
        if baseline_peak_mib
        else 0.0
    )
    if observed_delta is not None and observed_delta >= 0:
        recommendation = "do_not_repeat_observed_non_better_variant"
    elif max_group_hbm_mib >= failed_peak_mib * 0.98:
        recommendation = "blocked_near_observed_failed_peak_hbm"
    elif len(partition) > 7:
        recommendation = "do_not_run_more_group_switches_without_memory_change"
    elif peak_delta_pct < -10.0:
        recommendation = "capacity_probe_only_if_memory_plan_changes"
    else:
        recommendation = "deprioritized_no_clear_hbm_or_runtime_advantage"
    return {
        "group_ranges": ranges,
        "group_count": len(partition),
        "max_group_hbm_mib": round(max_group_hbm_mib, 3),
        "max_group_load_ms": round(max_group_load_ms, 3),
        "peak_hbm_delta_pct_vs_baseline": round(peak_delta_pct, 3),
        "final_logits_singleton_group": contains_final_singleton,
        "estimated_release_delta_ms": round(release_delta_ms, 3),
        "estimated_release_delta_ms_per_request": round_or_none(
            release_delta_ms / processed_request_count if processed_request_count else None,
            6,
        ),
        "observed_mb512_delta_ms_per_request": observed_delta,
        "recommendation": recommendation,
        "group_rows": group_rows,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    schedule = read_json(args.schedule_json)
    telemetry = read_json(args.load_telemetry_json)
    group_order = read_json(args.group_order_json)
    segments = segment_table(telemetry)
    if sorted(segments) != list(range(28)):
        raise RuntimeError("loaded_segments does not cover all 28 B4 segments")

    baseline_ranges = ["0:6", "6:12", "12:18", "18:24", "24:28"]
    observed = observed_variant_map(schedule)
    baseline = observed.get(run_key_from_ranges(baseline_ranges))
    if baseline is None:
        raise RuntimeError("mb512 5-group segment-major baseline not found")

    capacity = group_order.get("capacity_reference") or {}
    baseline_peak_mib = as_float(capacity.get("observed_success_peak_group_hbm_mib"))
    failed_peak_mib = as_float(capacity.get("observed_failed_g4_peak_group_hbm_mib"))
    if not baseline_peak_mib:
        baseline_peak_mib = max(
            sum((segments.get(index) or {}).get("hbm_size_mib", 0.0) for index in range(*parse_label(label)))
            for label in baseline_ranges
        )
    if not failed_peak_mib:
        failed_peak_mib = baseline_peak_mib * 1.12

    release_values = [
        as_float(group.get("group_release_ms"))
        for group in telemetry.get("group_rows") or []
        if as_float(group.get("group_release_ms")) > 0
    ]
    release_ms_per_group = sum(release_values) / len(release_values) if release_values else 0.0
    processed = as_int(baseline.get("processed_request_count")) or 2048
    baseline_ms = as_float(baseline.get("amortized_wall_ms_per_request"))

    candidates: list[dict[str, Any]] = []
    for group_count in range(args.min_group_count, args.max_group_count + 1):
        for partition in enumerate_partitions(
            start=0,
            end=28,
            group_count=group_count,
            min_group_segments=args.min_group_segments,
            max_group_segments=args.max_group_segments,
        ):
            candidates.append(
                partition_stats(
                    partition,
                    segments,
                    baseline_peak_mib,
                    failed_peak_mib,
                    observed,
                    baseline_ms,
                    release_ms_per_group,
                    processed,
                )
            )

    ranked = sorted(
        candidates,
        key=lambda row: (
            row["recommendation"] != "capacity_probe_only_if_memory_plan_changes",
            row["max_group_hbm_mib"],
            row["group_count"],
            row["estimated_release_delta_ms_per_request"],
        ),
    )
    observed_nonbaseline = [
        row
        for row in candidates
        if row.get("observed_mb512_delta_ms_per_request") is not None
        and row.get("group_ranges") != baseline_ranges
    ]
    recommendation_counts: dict[str, int] = {}
    for row in candidates:
        recommendation_counts[row["recommendation"]] = recommendation_counts.get(row["recommendation"], 0) + 1

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_group_partition_planner",
        "source_paths": {
            "schedule": str(args.schedule_json),
            "load_telemetry": str(args.load_telemetry_json),
            "group_order": str(args.group_order_json),
        },
        "inputs": {
            "segment_count": len(segments),
            "min_group_count": args.min_group_count,
            "max_group_count": args.max_group_count,
            "min_group_segments": args.min_group_segments,
            "max_group_segments": args.max_group_segments,
            "candidate_count": len(candidates),
            "release_ms_per_group": round(release_ms_per_group, 3),
        },
        "baseline": {
            "group_ranges": baseline_ranges,
            "ms_per_request": baseline.get("amortized_wall_ms_per_request"),
            "avg_bpu_loading": baseline.get("avg_bpu_loading"),
            "max_group_hbm_mib": round(baseline_peak_mib, 3),
        },
        "capacity_reference": {
            "observed_success_peak_group_hbm_mib": round(baseline_peak_mib, 3),
            "observed_failed_g4_peak_group_hbm_mib": round(failed_peak_mib, 3),
        },
        "recommendation_counts": recommendation_counts,
        "top_capacity_probe_candidates": ranked[:10],
        "observed_nonbaseline_variants": sorted(
            observed_nonbaseline,
            key=lambda row: as_float(row.get("observed_mb512_delta_ms_per_request")),
        ),
        "decision": {
            "systematic_partition_search_complete": True,
            "candidate_count": len(candidates),
            "run_new_partition_now": False,
            "only_probe_if_memory_plan_changes": (
                ranked[0]["group_ranges"] if ranked else None
            ),
            "reason": (
                "Systematic contiguous partition search finds lower-peak-HBM shapes, but observed "
                "mb512 non-baseline group variants are slower than the 5-group baseline and extra "
                "groups add release/switch overhead; use new partitions only as capacity probes after "
                "the memory plan changes."
            ),
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dream7B B4 Group Partition Planner",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- candidate_count: {payload['inputs']['candidate_count']}",
        f"- baseline_max_group_hbm_mib: {payload['baseline']['max_group_hbm_mib']}",
        f"- observed_failed_g4_peak_group_hbm_mib: {payload['capacity_reference']['observed_failed_g4_peak_group_hbm_mib']}",
        f"- run_new_partition_now: {payload['decision']['run_new_partition_now']}",
        f"- reason: {payload['decision']['reason']}",
        "",
        "## Recommendation Counts",
        "",
    ]
    for key, value in sorted(payload["recommendation_counts"].items()):
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Top Capacity Probe Candidates",
            "",
            "| rank | groups | max HBM MiB | peak delta % | release delta ms/request | observed delta ms/request | recommendation |",
            "| ---: | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for rank, row in enumerate(payload["top_capacity_probe_candidates"], start=1):
        lines.append(
            f"| {rank} | {','.join(row['group_ranges'])} | {row['max_group_hbm_mib']} | "
            f"{row['peak_hbm_delta_pct_vs_baseline']} | {row['estimated_release_delta_ms_per_request']} | "
            f"{row['observed_mb512_delta_ms_per_request']} | {row['recommendation']} |"
        )
    lines.extend(
        [
            "",
            "## Observed Nonbaseline Variants",
            "",
            "| groups | max HBM MiB | observed delta ms/request | recommendation |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for row in payload["observed_nonbaseline_variants"]:
        lines.append(
            f"| {','.join(row['group_ranges'])} | {row['max_group_hbm_mib']} | "
            f"{row['observed_mb512_delta_ms_per_request']} | {row['recommendation']} |"
        )
    lines.extend(["", "## Source Paths", ""])
    lines.extend(f"- {key}: {value}" for key, value in payload["source_paths"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Enumerate B4 contiguous group partitions from loaded_segments evidence.")
    parser.add_argument("--schedule-json", type=Path, default=DEFAULT_SCHEDULE)
    parser.add_argument("--load-telemetry-json", type=Path, default=DEFAULT_LOAD_TELEMETRY)
    parser.add_argument("--group-order-json", type=Path, default=DEFAULT_GROUP_ORDER)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    parser.add_argument("--min-group-count", type=int, default=5)
    parser.add_argument("--max-group-count", type=int, default=8)
    parser.add_argument("--min-group-segments", type=int, default=1)
    parser.add_argument("--max-group-segments", type=int, default=6)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
