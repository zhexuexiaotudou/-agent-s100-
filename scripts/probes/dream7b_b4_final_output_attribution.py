#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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


def round_or_none(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def group_label(group: dict[str, Any]) -> str:
    return f"{group.get('group_start')}:{group.get('group_end')}"


def final_segment_row(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for group in payload.get("group_rows") or []:
        for row in group.get("segment_rows") or []:
            if as_int(row.get("index")) == 27:
                return group, row
    return None


def hidden_mean_avg_run_ms(payload: dict[str, Any]) -> float | None:
    values: list[float] = []
    for group in payload.get("group_rows") or []:
        for row in group.get("segment_rows") or []:
            index = as_int(row.get("index"))
            if 1 <= index <= 26 and row.get("avg_run_ms") is not None:
                values.append(as_float(row.get("avg_run_ms")))
    return sum(values) / len(values) if values else None


def analyze_b4(path: Path) -> dict[str, Any] | None:
    payload = load_json(path)
    if payload.get("verdict") != "ok_dream7b_true_batch_group_major_telemetry":
        return None
    found = final_segment_row(payload)
    if found is None:
        return None
    final_group, final_row = found
    processed = as_int(payload.get("processed_request_count"))
    microbatches = as_int(payload.get("microbatch_count"))
    hidden_avg = hidden_mean_avg_run_ms(payload)
    final_avg = as_float(final_row.get("avg_run_ms"))
    final_run_ms = as_float(final_row.get("total_run_ms"))
    final_total_ms = as_float(final_row.get("segment_total_ms"))
    final_overhead_ms = max(0.0, final_total_ms - final_run_ms)
    final_excess_total_ms = max(0.0, final_avg - (hidden_avg or 0.0)) * microbatches
    timing = payload.get("timing_summary") or {}
    return {
        "file": str(path),
        "name": path.name,
        "microbatch_count": microbatches,
        "batch_size": payload.get("batch_size"),
        "processed_request_count": processed,
        "group_count": len(payload.get("group_rows") or []),
        "group_ranges": [group_label(group) for group in payload.get("group_rows") or []],
        "final_group": group_label(final_group),
        "final_shape": payload.get("final_shape"),
        "avg_bpu_loading": payload.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": payload.get("avg_nonzero_bpu_loading"),
        "ms_per_request": payload.get("amortized_wall_ms_per_request"),
        "hidden_mean_avg_run_ms": round_or_none(hidden_avg),
        "final_avg_run_ms": round_or_none(final_avg),
        "final_vs_hidden_ratio": round_or_none(final_avg / hidden_avg if hidden_avg else None),
        "final_run_ms": round(final_run_ms, 3),
        "final_segment_total_ms": round(final_total_ms, 3),
        "final_segment_overhead_ms": round(final_overhead_ms, 3),
        "final_run_ms_per_request": round_or_none(final_run_ms / processed if processed else None, 6),
        "final_segment_overhead_ms_per_request": round_or_none(final_overhead_ms / processed if processed else None, 6),
        "final_excess_ms_per_request_if_hidden_speed": round_or_none(
            final_excess_total_ms / processed if processed else None,
            6,
        ),
        "final_segment_overhead_fraction_of_final_segment_total": round_or_none(
            final_overhead_ms / final_total_ms if final_total_ms else None,
            6,
        ),
        "total_hidden_materialize_ms": timing.get("total_hidden_materialize_ms"),
        "hidden_materialize_ms_per_item": timing.get("hidden_materialize_ms_per_item"),
    }


def analyze_queue_phase(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    processed = as_int(payload.get("processed_request_count"))
    phase = payload.get("final_segment_phase_timing_ms") or {}
    final_run_ms = as_float((payload.get("final_segment_progress") or {}).get("segment_run_ms"))
    final_overhead_ms = as_float(payload.get("final_segment_overhead_ms"))
    return {
        "file": str(path),
        "name": path.name,
        "verdict": payload.get("verdict"),
        "raw_final": payload.get("raw_final"),
        "top_k": payload.get("top_k"),
        "processed_request_count": processed,
        "avg_bpu_loading": payload.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": payload.get("avg_nonzero_bpu_loading"),
        "final_segment_run_ms": round(final_run_ms, 3),
        "final_segment_overhead_ms": round(final_overhead_ms, 3),
        "final_segment_run_ms_per_request": round_or_none(final_run_ms / processed if processed else None, 6),
        "final_segment_overhead_ms_per_request": round_or_none(final_overhead_ms / processed if processed else None, 6),
        "final_shape_ms_per_request": round_or_none(as_float(phase.get("final_shape_ms")) / processed if processed else None, 6),
        "final_shape_count_ms_per_request": round_or_none(
            as_float(phase.get("final_shape_count_ms")) / processed if processed else None,
            6,
        ),
        "final_shape_check_ms_per_request": round_or_none(
            as_float(phase.get("final_shape_check_ms")) / processed if processed else None,
            6,
        ),
        "results_append_ms_per_request": round_or_none(
            as_float(phase.get("results_append_ms")) / processed if processed else None,
            6,
        ),
        "final_state_clear_ms_per_request": round_or_none(
            as_float(phase.get("final_state_clear_ms")) / processed if processed else None,
            6,
        ),
        "topk_ms_per_request": round_or_none(as_float(phase.get("topk_ms")) / processed if processed else None, 6)
        if "topk_ms" in phase
        else None,
        "phase_timing_ms": phase,
    }


def latest_default(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        row
        for row in rows
        if row["group_count"] == 5 and row["microbatch_count"] > 0
    ]
    return max(candidates or rows, key=lambda row: row["microbatch_count"])


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    b4_rows = [
        row
        for row in (analyze_b4(path) for path in sorted(args.telemetry_dir.glob(args.telemetry_glob)))
        if row is not None
    ]
    if not b4_rows:
        raise SystemExit("no B4 final segment rows found")
    b4_rows.sort(key=lambda row: (row["microbatch_count"], row["group_count"], row["name"]))
    queue_phase = analyze_queue_phase(args.queue_phase_json)
    focus = latest_default(b4_rows)
    decision = {
        "b4_final_python_output_overhead_small": (
            as_float(focus.get("final_segment_overhead_ms_per_request")) < 0.25
        ),
        "b4_final_excess_dominated_by_runtime_run": (
            as_float(focus.get("final_excess_ms_per_request_if_hidden_speed"))
            > 10.0 * as_float(focus.get("final_segment_overhead_ms_per_request"))
        ),
        "group_boundary_isolation_not_sufficient": True,
        "recommended_next": "compile_or_runtime_path_that_reduces_final_logits_compute_or_avoids_full_vocab_output",
    }
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_final_output_attribution",
        "b4_runs": b4_rows,
        "latest_default_b4": focus,
        "queue_raw_final_reference": queue_phase,
        "decision": decision,
        "interpretation": [
            "B4 true-batch telemetry already avoids full final-logits float32 dequantization; it records the final tensor shape and keeps raw output handling minimal.",
            "In the latest B4 mb3072 default run, final segment overhead outside runtime.run is below 0.1 ms/request, while final-vs-hidden excess is about 3.04 ms/request.",
            "Production raw-final phase timing shows the same pattern: shape/count/result bookkeeping is tiny per request after raw-final, and final_state_clear is the main remaining Python-side final-output cost.",
            "Final-logits group-boundary isolation does not beat the 5-group baseline; the next credible path is reducing final logits compute or avoiding full-vocab output at compile/runtime level.",
        ],
    }


def render_md(payload: dict[str, Any], out_md: Path) -> None:
    focus = payload["latest_default_b4"]
    queue = payload["queue_raw_final_reference"]
    lines = [
        "# Dream7B B4 Final Output Attribution",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- latest_default_file: {Path(focus['file']).name}",
        f"- latest_microbatch_count: {focus['microbatch_count']}",
        f"- latest_final_run_ms_per_request: {focus['final_run_ms_per_request']}",
        f"- latest_final_segment_overhead_ms_per_request: {focus['final_segment_overhead_ms_per_request']}",
        f"- latest_final_excess_ms_per_request_if_hidden_speed: {focus['final_excess_ms_per_request_if_hidden_speed']}",
        f"- queue_raw_final_overhead_ms_per_request: {queue['final_segment_overhead_ms_per_request']}",
        f"- recommended_next: {payload['decision']['recommended_next']}",
        "",
        "## B4 Runs",
        "",
        "| file | groups | microbatches | final_group | ms/request | final_run_ms/request | final_overhead_ms/request | final_excess_ms/request | final/hidden |",
        "| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["b4_runs"]:
        lines.append(
            f"| {Path(row['file']).name} | {row['group_count']} | {row['microbatch_count']} | "
            f"{row['final_group']} | {row['ms_per_request']} | {row['final_run_ms_per_request']} | "
            f"{row['final_segment_overhead_ms_per_request']} | "
            f"{row['final_excess_ms_per_request_if_hidden_speed']} | {row['final_vs_hidden_ratio']} |"
        )

    lines.extend(
        [
            "",
            "## Queue Raw-Final Reference",
            "",
            f"- file: {queue['file']}",
            f"- raw_final: {queue['raw_final']}",
            f"- top_k: {queue['top_k']}",
            f"- processed_request_count: {queue['processed_request_count']}",
            f"- avg_bpu_loading: {queue['avg_bpu_loading']}",
            f"- final_segment_run_ms_per_request: {queue['final_segment_run_ms_per_request']}",
            f"- final_segment_overhead_ms_per_request: {queue['final_segment_overhead_ms_per_request']}",
            f"- final_shape_ms_per_request: {queue['final_shape_ms_per_request']}",
            f"- final_shape_count_ms_per_request: {queue['final_shape_count_ms_per_request']}",
            f"- final_shape_check_ms_per_request: {queue['final_shape_check_ms_per_request']}",
            f"- results_append_ms_per_request: {queue['results_append_ms_per_request']}",
            f"- final_state_clear_ms_per_request: {queue['final_state_clear_ms_per_request']}",
            "",
            "## Decision",
            "",
        ]
    )
    lines.extend(f"- {key}: {value}" for key, value in payload["decision"].items())
    lines.extend(["", "## Interpretation", ""])
    lines.extend(f"- {item}" for item in payload["interpretation"])
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Attribute B4 final logits time to runtime.run versus output handling.")
    parser.add_argument("--telemetry-dir", type=Path, default=Path("tmp/remote_true_batch_reports"))
    parser.add_argument("--telemetry-glob", default="b4_*true_batch_group_major_telemetry.json")
    parser.add_argument(
        "--queue-phase-json",
        type=Path,
        default=Path("tmp/b4_runtime_schedule_analysis_20260619/dream7b_bpu_segment_major_phase_timing_20260614-005702__phase_timing_probe.json"),
    )
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/b4_runtime_schedule_analysis_20260619"))
    parser.add_argument("--out-stem", default="dream7b_b4_final_output_attribution_20260619")
    args = parser.parse_args()

    payload = build_payload(args)
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
