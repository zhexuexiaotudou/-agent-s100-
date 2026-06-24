#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except Exception:
        return 0


def as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def segment_from_error(error: str | None) -> str | None:
    if not error:
        return None
    match = re.search(r"/(seg\d{2}_\d{2})/", error)
    if match:
        return match.group(1)
    match = re.search(r"(seg\d{2}_\d{2})", error)
    return match.group(1) if match else None


def is_default_segment_major(row: dict[str, Any]) -> bool:
    return (
        row.get("inner_order") == "segment-major"
        and row.get("group_ranges") == ["0:6", "6:12", "12:18", "18:24", "24:28"]
        and not row.get("preallocate_hidden")
        and not row.get("prewarm_hbm")
        and row.get("release_gc_mode") == "collect"
    )


def has_gap_fields(row: dict[str, Any]) -> bool:
    return "gap_fields" in str(row.get("file") or "")


def build_payload(schedule: dict[str, Any], schedule_path: Path) -> dict[str, Any]:
    runs = list(schedule.get("b4_true_batch_runs") or [])
    default_runs = [row for row in runs if is_default_segment_major(row)]
    successful = [
        row
        for row in default_runs
        if row.get("verdict") == "ok_dream7b_true_batch_group_major_telemetry"
        and as_int(row.get("processed_request_count")) > 0
    ]
    failed = [
        row
        for row in default_runs
        if row.get("verdict") != "ok_dream7b_true_batch_group_major_telemetry"
        or as_int(row.get("processed_request_count")) == 0
    ]
    relevant_gap_failures = [
        row
        for row in runs
        if row.get("inner_order") == "segment-major"
        and not row.get("preallocate_hidden")
        and not row.get("prewarm_hbm")
        and row.get("release_gc_mode") == "collect"
        and has_gap_fields(row)
        and (
            row.get("verdict") != "ok_dream7b_true_batch_group_major_telemetry"
            or as_int(row.get("processed_request_count")) == 0
        )
    ]
    gap_success = [row for row in successful if has_gap_fields(row)]
    gap_failed = relevant_gap_failures
    latest_success = max(successful, key=lambda row: as_int(row.get("microbatch_count")), default={})
    latest_gap_success = max(gap_success, key=lambda row: as_int(row.get("microbatch_count")), default={})

    success_rows = [
        {
            "file": row.get("file"),
            "microbatch_count": row.get("microbatch_count"),
            "processed_request_count": row.get("processed_request_count"),
            "gap_fields_present": has_gap_fields(row),
            "avg_bpu_loading": row.get("avg_bpu_loading"),
            "avg_nonzero_bpu_loading": row.get("avg_nonzero_bpu_loading"),
            "ms_per_request": row.get("amortized_wall_ms_per_request"),
            "group_load_fraction_of_wall": row.get("group_load_fraction_of_wall"),
        }
        for row in sorted(successful, key=lambda item: as_int(item.get("microbatch_count")))
    ]
    failure_rows = []
    for row in sorted(failed + [row for row in relevant_gap_failures if row not in failed], key=lambda item: as_int(item.get("microbatch_count"))):
        error = next(iter(row.get("errors") or []), "")
        failure_rows.append(
            {
                "file": row.get("file"),
                "microbatch_count": row.get("microbatch_count"),
                "requested_group_count": len(row.get("group_ranges") or []),
                "completed_group_count": row.get("completed_group_count"),
                "completed_group_ranges": row.get("group_ranges"),
                "failed_segment": segment_from_error(error),
                "processed_request_count": row.get("processed_request_count"),
                "error": error,
            }
        )

    min_failed_gap_mb = min((as_int(row.get("microbatch_count")) for row in gap_failed), default=None)
    max_success_gap_mb = as_int(latest_gap_success.get("microbatch_count")) if latest_gap_success else None
    decision = {
        "gap_instrumented_success_boundary_microbatch_count": max_success_gap_mb,
        "gap_instrumented_first_failed_microbatch_count": min_failed_gap_mb,
        "do_not_continue_gap_microbatch_sweeps_above_success_boundary": bool(
            max_success_gap_mb and min_failed_gap_mb and min_failed_gap_mb > max_success_gap_mb
        ),
        "continue_prioritizing_final_logits_candidate": True,
        "queue_batch_remains_default": True,
        "reason": (
            "Gap-instrumented B=4 runs succeed through mb512 but fail at mb768/mb1024 in the current "
            "S100P memory state; longer microbatch-only sweeps are not the next useful lever."
        ),
    }
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_runtime_capacity_boundary",
        "source_paths": {"schedule": str(schedule_path)},
        "summary": {
            "default_segment_major_success_count": len(successful),
            "default_segment_major_failed_count": len(failed),
            "gap_instrumented_failed_count": len(relevant_gap_failures),
            "latest_successful_microbatch_count": latest_success.get("microbatch_count"),
            "latest_successful_ms_per_request": latest_success.get("amortized_wall_ms_per_request"),
            "latest_successful_avg_bpu_loading": latest_success.get("avg_bpu_loading"),
            "latest_gap_success_microbatch_count": latest_gap_success.get("microbatch_count"),
            "latest_gap_success_ms_per_request": latest_gap_success.get("amortized_wall_ms_per_request"),
            "latest_gap_success_avg_bpu_loading": latest_gap_success.get("avg_bpu_loading"),
            "first_gap_failure_microbatch_count": min_failed_gap_mb,
        },
        "successful_default_runs": success_rows,
        "failed_default_capacity_probes": failure_rows,
        "decision": decision,
    }


def render_md(payload: dict[str, Any], out_md: Path) -> None:
    summary = payload["summary"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B4 Runtime Capacity Boundary",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- latest_successful_microbatch_count: {summary['latest_successful_microbatch_count']}",
        f"- latest_gap_success_microbatch_count: {summary['latest_gap_success_microbatch_count']}",
        f"- first_gap_failure_microbatch_count: {summary['first_gap_failure_microbatch_count']}",
        f"- do_not_continue_gap_microbatch_sweeps_above_success_boundary: {decision['do_not_continue_gap_microbatch_sweeps_above_success_boundary']}",
        f"- continue_prioritizing_final_logits_candidate: {decision['continue_prioritizing_final_logits_candidate']}",
        "",
        "## Successful Default Runs",
        "",
        "| file | microbatches | requests | gap_fields | avg_bpu | nonzero_bpu | ms/request | load_share |",
        "| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["successful_default_runs"]:
        lines.append(
            f"| {Path(str(row.get('file'))).name} | {row.get('microbatch_count')} | "
            f"{row.get('processed_request_count')} | {row.get('gap_fields_present')} | "
            f"{row.get('avg_bpu_loading')} | {row.get('avg_nonzero_bpu_loading')} | "
            f"{row.get('ms_per_request')} | {row.get('group_load_fraction_of_wall')} |"
        )
    lines.extend(
        [
            "",
            "## Failed Default Capacity Probes",
            "",
            "| file | microbatches | completed_groups | failed_segment | processed_requests |",
            "| --- | ---: | ---: | --- | ---: |",
        ]
    )
    for row in payload["failed_default_capacity_probes"]:
        lines.append(
            f"| {Path(str(row.get('file'))).name} | {row.get('microbatch_count')} | "
            f"{row.get('completed_group_count')} | {row.get('failed_segment')} | "
            f"{row.get('processed_request_count')} |"
        )
    lines.extend(["", "## Decision", ""])
    lines.extend(f"- {key}: {value}" for key, value in decision.items())
    lines.extend(["", "## Source Paths", ""])
    lines.extend(f"- {key}: {value}" for key, value in payload["source_paths"].items())
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize B=4 true-batch runtime capacity boundaries.")
    parser.add_argument(
        "--schedule-json",
        type=Path,
        default=Path("tmp/b4_runtime_schedule_analysis_20260619/dream7b_true_batch_b4_schedule_analysis_current.json"),
    )
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/b4_runtime_schedule_analysis_20260619"))
    parser.add_argument("--out-stem", default="dream7b_b4_runtime_capacity_boundary_20260620")
    args = parser.parse_args()

    payload = build_payload(read_json(args.schedule_json), args.schedule_json)
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
