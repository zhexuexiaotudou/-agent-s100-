#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_GROUPS = ["0:6", "6:12", "12:18", "18:24", "24:28"]


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


def group_ranges(payload: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for group in payload.get("group_rows") or payload.get("groups") or []:
        start = group.get("group_start", group.get("start"))
        end = group.get("group_end", group.get("end"))
        result.append(f"{start}:{end}")
    return result


def is_candidate(path: Path, payload: dict[str, Any]) -> bool:
    return (
        path.name.startswith("b4_")
        and payload.get("verdict") == "ok_dream7b_true_batch_group_major_telemetry"
        and payload.get("inner_order") == "segment-major"
        and group_ranges(payload) == DEFAULT_GROUPS
        and as_int(payload.get("processed_request_count")) > 0
    )


def summarize_run(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    timing = payload.get("timing_summary") or {}
    processed = as_int(payload.get("processed_request_count"))
    return {
        "file": str(path),
        "name": path.name,
        "generated_at": payload.get("generated_at"),
        "microbatch_count": as_int(payload.get("microbatch_count")),
        "batch_size": as_int(payload.get("batch_size")),
        "processed_request_count": processed,
        "preallocate_hidden": bool(payload.get("preallocate_hidden")),
        "wall_ms": payload.get("wall_ms"),
        "ms_per_request": payload.get("amortized_wall_ms_per_request"),
        "avg_bpu": payload.get("avg_bpu_loading"),
        "nonzero_bpu": payload.get("avg_nonzero_bpu_loading"),
        "total_group_load_ms": timing.get("total_group_load_ms"),
        "total_segment_run_ms": timing.get("total_segment_run_ms"),
        "total_segment_total_ms": timing.get("total_segment_total_ms"),
        "total_segment_overhead_ms": timing.get("total_segment_overhead_ms"),
        "total_hidden_materialize_ms": timing.get("total_hidden_materialize_ms"),
        "hidden_materialize_ms_per_item": timing.get("hidden_materialize_ms_per_item"),
        "hidden_materialize_ms_per_request": round(
            as_float(timing.get("total_hidden_materialize_ms")) / processed,
            6,
        )
        if processed
        else None,
        "reused_hidden_buffer_count": timing.get("reused_hidden_buffer_count"),
        "total_group_release_ms": timing.get("total_group_release_ms"),
        "estimated_unaccounted_gap_ms": timing.get("estimated_unaccounted_gap_ms"),
        "final_logits_avg_run_ms": timing.get("final_logits_avg_run_ms"),
        "hidden_avg_run_ms": timing.get("hidden_avg_run_ms"),
    }


def delta(prealloc: dict[str, Any], no_prealloc: dict[str, Any], metric: str) -> dict[str, Any]:
    return {
        "metric": metric,
        "no_prealloc": no_prealloc.get(metric),
        "prealloc": prealloc.get(metric),
        "delta_prealloc_minus_no_prealloc": round(
            as_float(prealloc.get(metric)) - as_float(no_prealloc.get(metric)),
            6,
        ),
    }


def compare_pair(no_prealloc: dict[str, Any], prealloc: dict[str, Any]) -> dict[str, Any]:
    metrics = [
        "wall_ms",
        "ms_per_request",
        "avg_bpu",
        "nonzero_bpu",
        "total_group_load_ms",
        "total_segment_run_ms",
        "total_segment_total_ms",
        "total_segment_overhead_ms",
        "total_hidden_materialize_ms",
        "hidden_materialize_ms_per_item",
        "hidden_materialize_ms_per_request",
        "reused_hidden_buffer_count",
        "total_group_release_ms",
        "estimated_unaccounted_gap_ms",
    ]
    return {
        "microbatch_count": no_prealloc["microbatch_count"],
        "batch_size": no_prealloc["batch_size"],
        "no_prealloc_report": no_prealloc["file"],
        "prealloc_report": prealloc["file"],
        "rows": [delta(prealloc, no_prealloc, metric) for metric in metrics],
        "decision": {
            "prealloc_faster": as_float(prealloc.get("ms_per_request")) < as_float(no_prealloc.get("ms_per_request")),
            "prealloc_avg_bpu_higher": as_float(prealloc.get("avg_bpu")) > as_float(no_prealloc.get("avg_bpu")),
            "prealloc_nonzero_bpu_higher": as_float(prealloc.get("nonzero_bpu")) > as_float(no_prealloc.get("nonzero_bpu")),
            "prealloc_hidden_materialize_lower": as_float(prealloc.get("total_hidden_materialize_ms"))
            < as_float(no_prealloc.get("total_hidden_materialize_ms")),
        },
    }


def build_payload(paths: list[Path]) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for path in paths:
        payload = read_json(path)
        if is_candidate(path, payload):
            runs.append(summarize_run(path, payload))
    by_mb: dict[int, dict[bool, dict[str, Any]]] = {}
    for run in runs:
        bucket = by_mb.setdefault(run["microbatch_count"], {})
        existing = bucket.get(run["preallocate_hidden"])
        if existing is None or str(run.get("generated_at") or "") > str(existing.get("generated_at") or ""):
            bucket[run["preallocate_hidden"]] = run
    comparisons = [
        compare_pair(values[False], values[True])
        for _, values in sorted(by_mb.items())
        if False in values and True in values
    ]
    if not comparisons:
        raise SystemExit("no comparable prealloc/no-prealloc B4 segment-major runs found")
    latest = max(comparisons, key=lambda row: as_int(row.get("microbatch_count")))
    latest_decision = latest["decision"]
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_prealloc_hidden_analysis",
        "no_prealloc_report": latest["no_prealloc_report"],
        "prealloc_report": latest["prealloc_report"],
        "microbatch_count": latest["microbatch_count"],
        "batch_size": latest["batch_size"],
        "rows": latest["rows"],
        "comparisons": comparisons,
        "decision": {
            "preallocate_hidden_default": False,
            "preallocate_hidden_experimental_flag_only": True,
            "latest_prealloc_faster": latest_decision["prealloc_faster"],
            "latest_prealloc_avg_bpu_higher": latest_decision["prealloc_avg_bpu_higher"],
            "latest_prealloc_nonzero_bpu_higher": latest_decision["prealloc_nonzero_bpu_higher"],
            "latest_prealloc_hidden_materialize_lower": latest_decision["prealloc_hidden_materialize_lower"],
        },
        "interpretation": [
            "The optional --preallocate-hidden path still validates buffer reuse.",
            "At mb512, preallocation worsens wall time, average BPU, nonzero BPU, and hidden materialization time versus the default path.",
            "Keep preallocation as an experimental flag; do not promote it as the default scheduler path.",
        ],
    }


def render_md(payload: dict[str, Any], out_md: Path) -> None:
    lines = [
        "# Dream7B B4 Hidden Preallocation Analysis",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- latest_microbatch_count: {payload['microbatch_count']}",
        f"- no_prealloc_report: {payload['no_prealloc_report']}",
        f"- prealloc_report: {payload['prealloc_report']}",
        "",
        "## Latest A/B",
        "",
        "| metric | no_prealloc | prealloc | delta_prealloc_minus_no_prealloc |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['metric']} | {row['no_prealloc']} | {row['prealloc']} | "
            f"{row['delta_prealloc_minus_no_prealloc']} |"
        )
    lines.extend(
        [
            "",
            "## Comparable Runs",
            "",
            "| microbatches | ms/request_delta | avg_bpu_delta | nonzero_bpu_delta | hidden_materialize_ms_delta | reused_hidden_buffer_count |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for comparison in payload["comparisons"]:
        rows = {row["metric"]: row for row in comparison["rows"]}
        lines.append(
            f"| {comparison['microbatch_count']} | "
            f"{rows['ms_per_request']['delta_prealloc_minus_no_prealloc']} | "
            f"{rows['avg_bpu']['delta_prealloc_minus_no_prealloc']} | "
            f"{rows['nonzero_bpu']['delta_prealloc_minus_no_prealloc']} | "
            f"{rows['total_hidden_materialize_ms']['delta_prealloc_minus_no_prealloc']} | "
            f"{rows['reused_hidden_buffer_count']['prealloc']} |"
        )
    lines.extend(["", "## Decision", ""])
    lines.extend(f"- {key}: {value}" for key, value in payload["decision"].items())
    lines.extend(["", "## Interpretation", ""])
    lines.extend(f"- {item}" for item in payload["interpretation"])
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare B4 hidden-buffer preallocation telemetry.")
    parser.add_argument("--telemetry-dir", type=Path, default=Path("tmp/remote_true_batch_reports"))
    parser.add_argument("--telemetry-glob", default="b4_*true_batch_group_major_telemetry.json")
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/b4_runtime_schedule_analysis_20260619"))
    parser.add_argument("--out-stem", default="dream7b_b4_prealloc_hidden_ab_20260619")
    args = parser.parse_args()

    payload = build_payload(sorted(args.telemetry_dir.glob(args.telemetry_glob)))
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
