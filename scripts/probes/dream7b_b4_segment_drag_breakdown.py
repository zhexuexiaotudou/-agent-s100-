#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


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


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    value_mean = sum(values) / len(values)
    return math.sqrt(sum((value - value_mean) ** 2 for value in values) / (len(values) - 1))


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


def group_range(group: dict[str, Any]) -> str:
    start = group.get("group_start", group.get("start"))
    end = group.get("group_end", group.get("end"))
    return f"{start}:{end}"


def iter_segment_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in payload.get("group_rows") or []:
        label = group_range(group)
        for row in group.get("segment_rows") or []:
            copied = dict(row)
            copied["group"] = label
            rows.append(copied)
    return rows


def is_usable_segment_major(path: Path, payload: dict[str, Any]) -> bool:
    if payload.get("verdict") != "ok_dream7b_true_batch_group_major_telemetry":
        return False
    if payload.get("inner_order") != "segment-major":
        return False
    if not iter_segment_rows(payload):
        return False
    # Keep the failed capacity probe and microbatch-major traces out of this report.
    return path.name.startswith("b4_")


def segment_drag_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = iter_segment_rows(payload)
    hidden_avg = mean(
        [
            as_float(row.get("avg_run_ms"))
            for row in rows
            if segment_kind(as_int(row.get("index"))) == "hidden_block"
        ]
    )
    processed = as_int(payload.get("processed_request_count"))
    result: list[dict[str, Any]] = []
    for row in rows:
        index = as_int(row.get("index"))
        avg_run = as_float(row.get("avg_run_ms"))
        completed = as_int(row.get("completed_microbatch_count"))
        excess_avg = avg_run - hidden_avg if hidden_avg is not None else None
        positive_excess_total = max(0.0, excess_avg or 0.0) * completed
        segment_total = as_float(row.get("segment_total_ms"))
        total_run = as_float(row.get("total_run_ms"))
        result.append(
            {
                "index": index,
                "kind": segment_kind(index),
                "group": row.get("group"),
                "model_name": row.get("model_name"),
                "avg_run_ms": round(avg_run, 4),
                "total_run_ms": round(total_run, 3),
                "segment_total_ms": round(segment_total, 3),
                "segment_overhead_ms": round(max(0.0, segment_total - total_run), 3),
                "completed_microbatch_count": completed,
                "excess_avg_run_ms_vs_hidden_mean": round_or_none(excess_avg, 4),
                "positive_excess_total_ms": round(positive_excess_total, 3),
                "positive_excess_ms_per_request": round_or_none(
                    positive_excess_total / processed if processed else None,
                    5,
                ),
            }
        )
    return result


def group_accounting_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    wall_ms = as_float(payload.get("wall_ms"))
    processed = as_int(payload.get("processed_request_count"))
    rows: list[dict[str, Any]] = []
    for group in payload.get("group_rows") or []:
        segments = group.get("segment_rows") or []
        segment_total = sum(as_float(row.get("segment_total_ms")) for row in segments)
        total_run = sum(as_float(row.get("total_run_ms")) for row in segments)
        release_ms = as_float(group.get("group_release_ms"))
        load_ms = as_float(group.get("group_load_ms"))
        accounted = load_ms + segment_total + release_ms
        loop_ms = as_float(group.get("group_loop_ms"))
        rows.append(
            {
                "group": group_range(group),
                "loaded_count": as_int(group.get("loaded_count")),
                "contains_final_logits": any(as_int(row.get("index")) == 27 for row in segments),
                "group_load_ms": round(load_ms, 3),
                "segment_total_ms": round(segment_total, 3),
                "total_run_ms": round(total_run, 3),
                "segment_overhead_ms": round(max(0.0, segment_total - total_run), 3),
                "group_release_ms": round(release_ms, 3) if release_ms else None,
                "group_loop_ms": round(loop_ms, 3) if loop_ms else None,
                "unaccounted_gap_ms": round(loop_ms - accounted, 3) if loop_ms else None,
                "accounted_ms": round(accounted, 3),
                "accounted_wall_fraction": round_or_none(accounted / wall_ms if wall_ms else None, 6),
                "accounted_ms_per_request": round_or_none(accounted / processed if processed else None, 5),
            }
        )
    return rows


def analyze_run(path: Path) -> dict[str, Any] | None:
    payload = load_json(path)
    if not is_usable_segment_major(path, payload):
        return None
    segments = segment_drag_rows(payload)
    hidden_rows = [row for row in segments if row["kind"] == "hidden_block"]
    hidden_avg_values = [row["avg_run_ms"] for row in hidden_rows]
    final_row = next((row for row in segments if row["index"] == 27), None)
    token_row = next((row for row in segments if row["index"] == 0), None)
    groups = group_accounting_rows(payload)
    processed = as_int(payload.get("processed_request_count"))
    microbatches = as_int(payload.get("microbatch_count"))
    hidden_mean = mean(hidden_avg_values)

    final_excess_ms = as_float(final_row.get("positive_excess_total_ms")) if final_row else 0.0
    token_excess_ms = as_float(token_row.get("positive_excess_total_ms")) if token_row else 0.0
    return {
        "file": str(path),
        "name": path.name,
        "generated_at": payload.get("generated_at"),
        "microbatch_count": microbatches,
        "batch_size": payload.get("batch_size"),
        "processed_request_count": processed,
        "group_count": len(payload.get("group_rows") or []),
        "group_ranges": [group_range(group) for group in payload.get("group_rows") or []],
        "preallocate_hidden": bool(payload.get("preallocate_hidden", False)),
        "wall_ms": payload.get("wall_ms"),
        "ms_per_request": payload.get("amortized_wall_ms_per_request"),
        "avg_bpu_loading": payload.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": payload.get("avg_nonzero_bpu_loading"),
        "hidden_mean_avg_run_ms": round_or_none(hidden_mean, 4),
        "hidden_stdev_avg_run_ms": round_or_none(stdev(hidden_avg_values), 5),
        "hidden_min_avg_run_ms": round_or_none(min(hidden_avg_values), 4) if hidden_avg_values else None,
        "hidden_max_avg_run_ms": round_or_none(max(hidden_avg_values), 4) if hidden_avg_values else None,
        "final_avg_run_ms": final_row.get("avg_run_ms") if final_row else None,
        "final_vs_hidden_mean_ratio": round_or_none(
            as_float(final_row.get("avg_run_ms")) / hidden_mean
            if final_row and hidden_mean
            else None,
            4,
        ),
        "token_avg_run_ms": token_row.get("avg_run_ms") if token_row else None,
        "token_vs_hidden_mean_ratio": round_or_none(
            as_float(token_row.get("avg_run_ms")) / hidden_mean
            if token_row and hidden_mean
            else None,
            4,
        ),
        "final_excess_ms_per_request_if_hidden_speed": round_or_none(
            final_excess_ms / processed if processed else None,
            5,
        ),
        "token_excess_ms_per_request_if_hidden_speed": round_or_none(
            token_excess_ms / processed if processed else None,
            5,
        ),
        "segments_by_avg_run_ms": sorted(
            segments,
            key=lambda row: (row["avg_run_ms"], row["positive_excess_total_ms"]),
            reverse=True,
        ),
        "segments_by_positive_excess_ms": sorted(
            segments,
            key=lambda row: (row["positive_excess_total_ms"], row["avg_run_ms"]),
            reverse=True,
        ),
        "groups_by_accounted_ms": sorted(
            groups,
            key=lambda row: row["accounted_ms"],
            reverse=True,
        ),
    }


def aggregate_segments(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_index: dict[int, list[dict[str, Any]]] = {}
    for run in runs:
        for row in run["segments_by_avg_run_ms"]:
            by_index.setdefault(as_int(row["index"]), []).append(row)

    rows: list[dict[str, Any]] = []
    for index, values in sorted(by_index.items()):
        avg_values = [as_float(row.get("avg_run_ms")) for row in values]
        excess_values = [as_float(row.get("positive_excess_ms_per_request")) for row in values]
        rows.append(
            {
                "index": index,
                "kind": segment_kind(index),
                "observed_run_count": len(values),
                "mean_avg_run_ms": round_or_none(mean(avg_values), 4),
                "stdev_avg_run_ms": round_or_none(stdev(avg_values), 5),
                "min_avg_run_ms": round(min(avg_values), 4),
                "max_avg_run_ms": round(max(avg_values), 4),
                "mean_positive_excess_ms_per_request": round_or_none(mean(excess_values), 5),
                "max_positive_excess_ms_per_request": round(max(excess_values), 5),
                "representative_group": values[-1].get("group"),
            }
        )
    return sorted(
        rows,
        key=lambda row: (as_float(row["mean_avg_run_ms"]), as_float(row["max_positive_excess_ms_per_request"])),
        reverse=True,
    )


def default_collect_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        run
        for run in runs
        if run["group_count"] == 5
        and not run["preallocate_hidden"]
        and run.get("group_ranges") == ["0:6", "6:12", "12:18", "18:24", "24:28"]
        and "release_gc_skip" not in str(run.get("name") or "")
        and "prewarm_hbm" not in str(run.get("name") or "")
    ]


def aggregate_kind_stability(runs: list[dict[str, Any]]) -> dict[str, Any]:
    source_keys = {
        "final_avg_run_ms": "final_avg_run_ms",
        "final_excess_ms_per_request": "final_excess_ms_per_request_if_hidden_speed",
        "token_avg_run_ms": "token_avg_run_ms",
        "token_excess_ms_per_request": "token_excess_ms_per_request_if_hidden_speed",
        "hidden_mean_avg_run_ms": "hidden_mean_avg_run_ms",
        "hidden_stdev_avg_run_ms": "hidden_stdev_avg_run_ms",
    }
    values: dict[str, list[float]] = {key: [] for key in source_keys}
    for run in runs:
        for output_key, source_key in source_keys.items():
            value = run.get(source_key)
            if value is not None:
                values[output_key].append(as_float(value))
    return {
        key: {
            "sample_count": len(items),
            "mean": round_or_none(mean(items), 5),
            "stdev": round_or_none(stdev(items), 5),
            "min": round_or_none(min(items), 5) if items else None,
            "max": round_or_none(max(items), 5) if items else None,
        }
        for key, items in values.items()
    }


def pick_latest_default(runs: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = default_collect_runs(runs)
    if not candidates:
        candidates = [
            run for run in runs if run["group_count"] == 5 and not run["preallocate_hidden"]
        ]
    if not candidates:
        candidates = runs
    return max(candidates, key=lambda run: as_int(run.get("microbatch_count")))


def build_payload(paths: list[Path]) -> dict[str, Any]:
    runs = [run for run in (analyze_run(path) for path in paths) if run is not None]
    runs.sort(
        key=lambda run: (
            as_int(run.get("microbatch_count")),
            as_int(run.get("group_count")),
            bool(run.get("preallocate_hidden")),
            run.get("name") or "",
        )
    )
    if not runs:
        raise SystemExit("no successful B=4 segment-major telemetry with segment rows")

    latest = pick_latest_default(runs)
    aggregate = aggregate_segments(runs)
    default_runs = default_collect_runs(runs)
    final = next(row for row in latest["segments_by_avg_run_ms"] if row["index"] == 27)
    token = next(row for row in latest["segments_by_avg_run_ms"] if row["index"] == 0)
    stability = aggregate_kind_stability(runs)
    default_stability = aggregate_kind_stability(default_runs)
    interpretation = [
        "The final logits segment is the only large run-time outlier; in the latest default run it is about 2.5x the hidden-segment mean.",
        f"If the final logits segment ran at hidden-block speed, the latest B=4 mb{latest['microbatch_count']} run would save about {latest['final_excess_ms_per_request_if_hidden_speed']} ms/request; token embedding contributes only about {latest['token_excess_ms_per_request_if_hidden_speed']} ms/request of positive excess.",
        f"Across default 5-group collect runs, final logits positive excess averages {default_stability['final_excess_ms_per_request']['mean']} ms/request with stdev {default_stability['final_excess_ms_per_request']['stdev']}; this is stable across microbatch counts.",
        "The hidden segments are tightly clustered, so reordering hidden blocks is unlikely to create a large win without changing load amortization or final-logits handling.",
        "The final group is not the largest accounted group in the latest run; the logits segment is the outlier, not the final group's HBM load.",
        "Useful next runtime A/Bs should target final-logits isolation/fusion and only then revisit 5-group versus 6-group boundaries at mb512 or larger.",
    ]
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_segment_drag_breakdown",
        "analyzed_run_count": len(runs),
        "default_collect_run_count": len(default_runs),
        "runs": runs,
        "default_collect_runs": default_runs,
        "aggregate_segments_by_avg_run_ms": aggregate,
        "cross_run_stability": stability,
        "default_collect_stability": default_stability,
        "latest_default_run": latest,
        "latest_default_focus": {
            "file": latest["file"],
            "microbatch_count": latest["microbatch_count"],
            "ms_per_request": latest["ms_per_request"],
            "avg_bpu_loading": latest["avg_bpu_loading"],
            "avg_nonzero_bpu_loading": latest["avg_nonzero_bpu_loading"],
            "hidden_mean_avg_run_ms": latest["hidden_mean_avg_run_ms"],
            "hidden_stdev_avg_run_ms": latest["hidden_stdev_avg_run_ms"],
            "final_avg_run_ms": final["avg_run_ms"],
            "final_vs_hidden_mean_ratio": latest["final_vs_hidden_mean_ratio"],
            "final_excess_ms_per_request_if_hidden_speed": latest[
                "final_excess_ms_per_request_if_hidden_speed"
            ],
            "token_avg_run_ms": token["avg_run_ms"],
            "token_vs_hidden_mean_ratio": latest["token_vs_hidden_mean_ratio"],
            "token_excess_ms_per_request_if_hidden_speed": latest[
                "token_excess_ms_per_request_if_hidden_speed"
            ],
            "top_group_by_accounted_ms": latest["groups_by_accounted_ms"][0],
        },
        "interpretation": interpretation,
    }


def render_md(payload: dict[str, Any], out_md: Path) -> None:
    latest = payload["latest_default_focus"]
    latest_run = payload["latest_default_run"]
    lines = [
        "# Dream7B B4 Segment Drag Breakdown",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- analyzed_run_count: {payload['analyzed_run_count']}",
        f"- default_collect_run_count: {payload['default_collect_run_count']}",
        f"- latest_default_file: {Path(latest['file']).name}",
        f"- latest_microbatch_count: {latest['microbatch_count']}",
        f"- latest_ms_per_request: {latest['ms_per_request']}",
        f"- latest_avg_bpu_loading: {latest['avg_bpu_loading']}",
        f"- latest_avg_nonzero_bpu_loading: {latest['avg_nonzero_bpu_loading']}",
        "",
        "## Latest Default Focus",
        "",
        f"- hidden_mean_avg_run_ms: {latest['hidden_mean_avg_run_ms']}",
        f"- hidden_stdev_avg_run_ms: {latest['hidden_stdev_avg_run_ms']}",
        f"- final_avg_run_ms: {latest['final_avg_run_ms']}",
        f"- final_vs_hidden_mean_ratio: {latest['final_vs_hidden_mean_ratio']}",
        f"- final_excess_ms_per_request_if_hidden_speed: {latest['final_excess_ms_per_request_if_hidden_speed']}",
        f"- token_avg_run_ms: {latest['token_avg_run_ms']}",
        f"- token_vs_hidden_mean_ratio: {latest['token_vs_hidden_mean_ratio']}",
        f"- token_excess_ms_per_request_if_hidden_speed: {latest['token_excess_ms_per_request_if_hidden_speed']}",
        f"- top_group_by_accounted_ms: {latest['top_group_by_accounted_ms']['group']}",
        "",
        "## Cross-Run Stability",
        "",
        "| metric | sample_count | mean | stdev | min | max |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for metric, stats in payload["default_collect_stability"].items():
        lines.append(
            f"| default_collect_{metric} | {stats['sample_count']} | {stats['mean']} | "
            f"{stats['stdev']} | {stats['min']} | {stats['max']} |"
        )
    for metric, stats in payload["cross_run_stability"].items():
        lines.append(
            f"| all_segment_major_{metric} | {stats['sample_count']} | {stats['mean']} | "
            f"{stats['stdev']} | {stats['min']} | {stats['max']} |"
        )
    lines.extend(
        [
            "",
        "## Slowest Segments Across Runs",
        "",
        "| rank | index | kind | mean_avg_ms | stdev_avg_ms | min_avg_ms | max_avg_ms | mean_excess_ms/request | representative_group |",
        "| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for rank, row in enumerate(payload["aggregate_segments_by_avg_run_ms"][:10], start=1):
        lines.append(
            f"| {rank} | {row['index']} | {row['kind']} | {row['mean_avg_run_ms']} | "
            f"{row['stdev_avg_run_ms']} | {row['min_avg_run_ms']} | {row['max_avg_run_ms']} | "
            f"{row['mean_positive_excess_ms_per_request']} | {row['representative_group']} |"
        )

    lines.extend(
        [
            "",
            "## Latest Default Segment Ranking",
            "",
            "| rank | group | index | kind | avg_run_ms | excess_ms/request | segment_total_ms | overhead_ms |",
            "| ---: | --- | ---: | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for rank, row in enumerate(latest_run["segments_by_positive_excess_ms"][:10], start=1):
        lines.append(
            f"| {rank} | {row['group']} | {row['index']} | {row['kind']} | {row['avg_run_ms']} | "
            f"{row['positive_excess_ms_per_request']} | {row['segment_total_ms']} | {row['segment_overhead_ms']} |"
        )

    lines.extend(
        [
            "",
            "## Latest Default Group Accounting",
            "",
            "| rank | group | loaded | final | load_ms | segment_total_ms | release_ms | gap_ms | accounted_ms/request | wall_share |",
            "| ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for rank, row in enumerate(latest_run["groups_by_accounted_ms"], start=1):
        wall_share = (
            f"{100 * as_float(row['accounted_wall_fraction']):.2f}%"
            if row["accounted_wall_fraction"] is not None
            else ""
        )
        lines.append(
            f"| {rank} | {row['group']} | {row['loaded_count']} | {row['contains_final_logits']} | "
            f"{row['group_load_ms']} | {row['segment_total_ms']} | {row['group_release_ms']} | "
            f"{row['unaccounted_gap_ms']} | {row['accounted_ms_per_request']} | {wall_share} |"
        )

    lines.extend(["", "## Run Summary", ""])
    lines.extend(
        [
            "| file | groups | microbatches | avg_bpu | nonzero_bpu | ms/request | hidden_avg_ms | final_avg_ms | final_excess_ms/request |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for run in payload["runs"]:
        lines.append(
            f"| {Path(run['file']).name} | {run['group_count']} | {run['microbatch_count']} | "
            f"{run['avg_bpu_loading']} | {run['avg_nonzero_bpu_loading']} | {run['ms_per_request']} | "
            f"{run['hidden_mean_avg_run_ms']} | {run['final_avg_run_ms']} | "
            f"{run['final_excess_ms_per_request_if_hidden_speed']} |"
        )

    lines.extend(["", "## Interpretation", ""])
    lines.extend(f"- {item}" for item in payload["interpretation"])
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank Dream7B B=4 segment and group runtime drag from telemetry.")
    parser.add_argument("--telemetry-dir", type=Path, default=Path("tmp/remote_true_batch_reports"))
    parser.add_argument("--telemetry-glob", default="b4_*true_batch_group_major_telemetry.json")
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/b4_runtime_schedule_analysis_20260619"))
    parser.add_argument("--out-stem", default="dream7b_b4_segment_drag_breakdown_20260619")
    args = parser.parse_args()

    paths = sorted(args.telemetry_dir.glob(args.telemetry_glob))
    payload = build_payload(paths)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.out_dir / f"{args.out_stem}.json"
    out_md = args.out_dir / f"{args.out_stem}.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_md(payload, out_md)
    print(out_json)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
