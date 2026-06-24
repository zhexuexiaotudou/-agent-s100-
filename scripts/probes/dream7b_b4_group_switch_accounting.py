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


def round_or_none(value: float | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def group_label(group: dict[str, Any]) -> str:
    return f"{group.get('group_start', group.get('start'))}:{group.get('group_end', group.get('end'))}"


def iter_segment_rows(group: dict[str, Any]) -> list[dict[str, Any]]:
    return list(group.get("segment_rows") or [])


def segment_kind(index: int) -> str:
    if index == 0:
        return "token_embedding"
    if index == 27:
        return "final_logits"
    return "hidden_block"


def is_successful_b4_segment_major(path: Path, payload: dict[str, Any]) -> bool:
    return (
        path.name.startswith("b4_")
        and payload.get("verdict") == "ok_dream7b_true_batch_group_major_telemetry"
        and payload.get("inner_order") == "segment-major"
        and as_int(payload.get("processed_request_count")) > 0
        and bool(payload.get("group_rows"))
    )


def segment_totals(groups: list[dict[str, Any]]) -> dict[str, float]:
    total_run = 0.0
    total_segment = 0.0
    hidden_materialize = 0.0
    inter_segment_first_run_gap = 0.0
    intra_segment_run_gap = 0.0
    final_run = 0.0
    hidden_run_values: list[float] = []
    final_completed = 0
    final_avg = None
    for group in groups:
        for row in iter_segment_rows(group):
            index = as_int(row.get("index"))
            run_ms = as_float(row.get("total_run_ms"))
            segment_ms = as_float(row.get("segment_total_ms"))
            total_run += run_ms
            total_segment += segment_ms
            hidden_materialize += as_float(row.get("hidden_materialize_ms"))
            inter_segment_first_run_gap += as_float(row.get("inter_segment_first_run_gap_ms"))
            intra_segment_run_gap += as_float(row.get("intra_segment_run_gap_ms"))
            if segment_kind(index) == "hidden_block":
                hidden_run_values.append(as_float(row.get("avg_run_ms")))
            if index == 27:
                final_run = run_ms
                final_avg = as_float(row.get("avg_run_ms"))
                final_completed = as_int(row.get("completed_microbatch_count"))
    hidden_mean = sum(hidden_run_values) / len(hidden_run_values) if hidden_run_values else 0.0
    final_excess = max(0.0, (final_avg or 0.0) - hidden_mean) * final_completed
    return {
        "total_segment_run_ms": total_run,
        "total_segment_total_ms": total_segment,
        "total_segment_overhead_ms": max(0.0, total_segment - total_run),
        "total_hidden_materialize_ms": hidden_materialize,
        "total_inter_segment_first_run_gap_ms": inter_segment_first_run_gap,
        "total_intra_segment_run_gap_ms": intra_segment_run_gap,
        "segment_overhead_excluding_hidden_materialize_ms": max(
            0.0, total_segment - total_run - hidden_materialize
        ),
        "segment_overhead_excluding_measured_gaps_ms": max(
            0.0,
            total_segment
            - total_run
            - hidden_materialize
            - inter_segment_first_run_gap
            - intra_segment_run_gap,
        ),
        "final_logits_total_run_ms": final_run,
        "final_logits_excess_ms_if_hidden_speed": final_excess,
        "hidden_mean_avg_run_ms": hidden_mean,
        "final_avg_run_ms": final_avg or 0.0,
    }


def analyze_run(path: Path) -> dict[str, Any] | None:
    payload = read_json(path)
    if not is_successful_b4_segment_major(path, payload):
        return None
    groups = list(payload.get("group_rows") or [])
    gap_fields_present = any(
        "inter_segment_first_run_gap_ms" in row or "intra_segment_run_gap_ms" in row
        for group in groups
        for row in iter_segment_rows(group)
    )
    processed = as_int(payload.get("processed_request_count"))
    wall_ms = as_float(payload.get("wall_ms"))
    timing = payload.get("timing_summary") or {}
    seg = segment_totals(groups)
    group_load = sum(as_float(group.get("group_load_ms")) for group in groups)
    group_release = sum(as_float(group.get("group_release_ms")) for group in groups)
    accounted = group_load + seg["total_segment_total_ms"] + group_release
    unaccounted = wall_ms - accounted
    switch_gap = max(0.0, group_release) + max(0.0, unaccounted)

    group_rows: list[dict[str, Any]] = []
    for group in groups:
        rows = iter_segment_rows(group)
        segment_total = sum(as_float(row.get("segment_total_ms")) for row in rows)
        segment_run = sum(as_float(row.get("total_run_ms")) for row in rows)
        hidden_materialize = sum(as_float(row.get("hidden_materialize_ms")) for row in rows)
        inter_segment_first_run_gap = sum(as_float(row.get("inter_segment_first_run_gap_ms")) for row in rows)
        intra_segment_run_gap = sum(as_float(row.get("intra_segment_run_gap_ms")) for row in rows)
        load_ms = as_float(group.get("group_load_ms"))
        release_ms = as_float(group.get("group_release_ms"))
        group_accounted = load_ms + segment_total + release_ms
        group_rows.append(
            {
                "group": group_label(group),
                "loaded_count": as_int(group.get("loaded_count")),
                "contains_final_logits": any(as_int(row.get("index")) == 27 for row in rows),
                "group_load_ms": round(load_ms, 3),
                "group_load_ms_per_request": round_or_none(load_ms / processed if processed else None, 6),
                "segment_total_ms": round(segment_total, 3),
                "segment_run_ms": round(segment_run, 3),
                "segment_overhead_ms": round(max(0.0, segment_total - segment_run), 3),
                "hidden_materialize_ms": round(hidden_materialize, 3),
                "inter_segment_first_run_gap_ms": round(inter_segment_first_run_gap, 3)
                if inter_segment_first_run_gap
                else None,
                "intra_segment_run_gap_ms": round(intra_segment_run_gap, 3) if intra_segment_run_gap else None,
                "segment_overhead_excluding_hidden_materialize_ms": round(
                    max(0.0, segment_total - segment_run - hidden_materialize), 3
                ),
                "segment_overhead_excluding_measured_gaps_ms": round(
                    max(
                        0.0,
                        segment_total
                        - segment_run
                        - hidden_materialize
                        - inter_segment_first_run_gap
                        - intra_segment_run_gap,
                    ),
                    3,
                ),
                "group_release_ms": round(release_ms, 3),
                "group_release_ms_per_request": round_or_none(release_ms / processed if processed else None, 6),
                "accounted_ms": round(group_accounted, 3),
                "accounted_ms_per_request": round_or_none(group_accounted / processed if processed else None, 6),
            }
        )

    return {
        "file": str(path),
        "name": path.name,
        "generated_at": payload.get("generated_at"),
        "microbatch_count": as_int(payload.get("microbatch_count")),
        "batch_size": as_int(payload.get("batch_size")),
        "processed_request_count": processed,
        "group_count": len(groups),
        "group_ranges": [group_label(group) for group in groups],
        "preallocate_hidden": bool(payload.get("preallocate_hidden", False)),
        "gap_fields_present": gap_fields_present,
        "wall_ms": round(wall_ms, 3),
        "ms_per_request": payload.get("amortized_wall_ms_per_request"),
        "avg_bpu_loading": payload.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": payload.get("avg_nonzero_bpu_loading"),
        "total_group_load_ms": round(group_load, 3),
        "total_group_release_ms": round(group_release, 3),
        "estimated_unaccounted_gap_ms": round(unaccounted, 3),
        "group_switch_gap_ms": round(switch_gap, 3),
        "group_switch_gap_ms_per_request": round_or_none(switch_gap / processed if processed else None, 6),
        "group_load_ms_per_request": round_or_none(group_load / processed if processed else None, 6),
        "group_release_ms_per_request": round_or_none(group_release / processed if processed else None, 6),
        "unaccounted_gap_ms_per_request": round_or_none(unaccounted / processed if processed else None, 6),
        "total_segment_overhead_ms": round(seg["total_segment_overhead_ms"], 3),
        "segment_overhead_ms_per_request": round_or_none(
            seg["total_segment_overhead_ms"] / processed if processed else None, 6
        ),
        "total_hidden_materialize_ms": round(seg["total_hidden_materialize_ms"], 3),
        "hidden_materialize_ms_per_request": round_or_none(
            seg["total_hidden_materialize_ms"] / processed if processed else None, 6
        ),
        "inter_segment_first_run_gap_ms_per_request": round_or_none(
            seg["total_inter_segment_first_run_gap_ms"] / processed if processed else None,
            6,
        ),
        "intra_segment_run_gap_ms_per_request": round_or_none(
            seg["total_intra_segment_run_gap_ms"] / processed if processed else None,
            6,
        ),
        "segment_overhead_excluding_hidden_materialize_ms": round(
            seg["segment_overhead_excluding_hidden_materialize_ms"], 3
        ),
        "segment_overhead_excluding_hidden_materialize_ms_per_request": round_or_none(
            seg["segment_overhead_excluding_hidden_materialize_ms"] / processed if processed else None,
            6,
        ),
        "segment_overhead_excluding_measured_gaps_ms_per_request": round_or_none(
            seg["segment_overhead_excluding_measured_gaps_ms"] / processed if processed else None,
            6,
        ),
        "final_logits_run_ms_per_request": round_or_none(
            seg["final_logits_total_run_ms"] / processed if processed else None,
            6,
        ),
        "final_logits_excess_ms_per_request_if_hidden_speed": round_or_none(
            seg["final_logits_excess_ms_if_hidden_speed"] / processed if processed else None,
            6,
        ),
        "hidden_mean_avg_run_ms": round_or_none(seg["hidden_mean_avg_run_ms"], 4),
        "final_avg_run_ms": round_or_none(seg["final_avg_run_ms"], 4),
        "timing_summary": timing,
        "groups": group_rows,
    }


def pick_latest_default(runs: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        run
        for run in runs
        if run["group_ranges"] == DEFAULT_GROUPS and not run.get("preallocate_hidden")
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
        raise SystemExit("no successful B=4 segment-major telemetry found")

    latest = pick_latest_default(runs)
    gap_runs = [run for run in runs if run.get("gap_fields_present")]
    latest_gap = max(gap_runs, key=lambda run: str(run.get("generated_at") or run.get("name") or "")) if gap_runs else None
    load_vs_switch_ratio = (
        as_float(latest.get("group_load_ms_per_request"))
        / as_float(latest.get("group_switch_gap_ms_per_request"))
        if as_float(latest.get("group_switch_gap_ms_per_request")) > 0
        else None
    )
    final_excess_vs_switch_ratio = (
        as_float(latest.get("final_logits_excess_ms_per_request_if_hidden_speed"))
        / as_float(latest.get("group_switch_gap_ms_per_request"))
        if as_float(latest.get("group_switch_gap_ms_per_request")) > 0
        else None
    )
    decision = {
        "group_release_and_unaccounted_gap_not_primary": (
            as_float(latest.get("group_switch_gap_ms_per_request")) < 0.1
        ),
        "hbm_group_load_is_fixed_amortization_not_active_bpu_fix": True,
        "segment_overhead_has_some_python_headroom_but_less_than_final_logits": (
            as_float(latest.get("segment_overhead_excluding_hidden_materialize_ms_per_request"))
            < as_float(latest.get("final_logits_excess_ms_per_request_if_hidden_speed"))
        ),
        "next_runtime_candidate": "seg27_28_last_token_logits",
        "scheduler_followup": "only revisit group caching/load policy if memory plan changes enough to keep more HBM groups resident",
    }
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_group_switch_accounting",
        "analyzed_run_count": len(runs),
        "runs": runs,
        "latest_default_run": latest,
        "latest_default_summary": {
            "file": latest["file"],
            "microbatch_count": latest["microbatch_count"],
            "processed_request_count": latest["processed_request_count"],
            "avg_bpu_loading": latest["avg_bpu_loading"],
            "avg_nonzero_bpu_loading": latest["avg_nonzero_bpu_loading"],
            "ms_per_request": latest["ms_per_request"],
            "group_load_ms_per_request": latest["group_load_ms_per_request"],
            "group_switch_gap_ms_per_request": latest["group_switch_gap_ms_per_request"],
            "group_release_ms_per_request": latest["group_release_ms_per_request"],
            "unaccounted_gap_ms_per_request": latest["unaccounted_gap_ms_per_request"],
            "segment_overhead_ms_per_request": latest["segment_overhead_ms_per_request"],
            "hidden_materialize_ms_per_request": latest["hidden_materialize_ms_per_request"],
            "inter_segment_first_run_gap_ms_per_request": latest["inter_segment_first_run_gap_ms_per_request"],
            "intra_segment_run_gap_ms_per_request": latest["intra_segment_run_gap_ms_per_request"],
            "segment_overhead_excluding_hidden_materialize_ms_per_request": latest[
                "segment_overhead_excluding_hidden_materialize_ms_per_request"
            ],
            "segment_overhead_excluding_measured_gaps_ms_per_request": latest[
                "segment_overhead_excluding_measured_gaps_ms_per_request"
            ],
            "final_logits_run_ms_per_request": latest["final_logits_run_ms_per_request"],
            "final_logits_excess_ms_per_request_if_hidden_speed": latest[
                "final_logits_excess_ms_per_request_if_hidden_speed"
            ],
            "group_load_to_switch_gap_ratio": round_or_none(load_vs_switch_ratio, 2),
            "final_excess_to_switch_gap_ratio": round_or_none(final_excess_vs_switch_ratio, 2),
        },
        "latest_gap_instrumented_summary": (
            {
                "file": latest_gap["file"],
                "microbatch_count": latest_gap["microbatch_count"],
                "processed_request_count": latest_gap["processed_request_count"],
                "avg_bpu_loading": latest_gap["avg_bpu_loading"],
                "avg_nonzero_bpu_loading": latest_gap["avg_nonzero_bpu_loading"],
                "ms_per_request": latest_gap["ms_per_request"],
                "inter_segment_first_run_gap_ms_per_request": latest_gap[
                    "inter_segment_first_run_gap_ms_per_request"
                ],
                "intra_segment_run_gap_ms_per_request": latest_gap["intra_segment_run_gap_ms_per_request"],
                "segment_overhead_excluding_measured_gaps_ms_per_request": latest_gap[
                    "segment_overhead_excluding_measured_gaps_ms_per_request"
                ],
                "final_logits_excess_ms_per_request_if_hidden_speed": latest_gap[
                    "final_logits_excess_ms_per_request_if_hidden_speed"
                ],
            }
            if latest_gap
            else None
        ),
        "decision": decision,
        "interpretation": [
            "At the latest default point, release plus unaccounted group-switch gap is tiny per request; it is not the main latency or BPU lever.",
            "The visible group-load cost is real but mostly fixed amortization from loading resident HBM groups, not an active compute-utilization fix.",
            "The segment loop has modest Python/materialization overhead, but final-logits compute excess remains the larger direct single-segment target.",
        ],
    }


def render_md(payload: dict[str, Any], out_md: Path) -> None:
    latest = payload["latest_default_summary"]
    latest_gap = payload.get("latest_gap_instrumented_summary")
    decision = payload["decision"]
    lines = [
        "# Dream7B B4 Group Switch Accounting",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- analyzed_run_count: {payload['analyzed_run_count']}",
        "",
        "## Latest Default Summary",
        "",
        f"- latest_default_file: {Path(latest['file']).name}",
        f"- microbatch_count: {latest['microbatch_count']}",
        f"- processed_request_count: {latest['processed_request_count']}",
        f"- avg_bpu_loading: {latest['avg_bpu_loading']}",
        f"- avg_nonzero_bpu_loading: {latest['avg_nonzero_bpu_loading']}",
        f"- ms_per_request: {latest['ms_per_request']}",
        f"- group_load_ms_per_request: {latest['group_load_ms_per_request']}",
        f"- group_switch_gap_ms_per_request: {latest['group_switch_gap_ms_per_request']}",
        f"- group_release_ms_per_request: {latest['group_release_ms_per_request']}",
        f"- unaccounted_gap_ms_per_request: {latest['unaccounted_gap_ms_per_request']}",
        f"- segment_overhead_ms_per_request: {latest['segment_overhead_ms_per_request']}",
        f"- hidden_materialize_ms_per_request: {latest['hidden_materialize_ms_per_request']}",
        f"- inter_segment_first_run_gap_ms_per_request: {latest['inter_segment_first_run_gap_ms_per_request']}",
        f"- intra_segment_run_gap_ms_per_request: {latest['intra_segment_run_gap_ms_per_request']}",
        f"- segment_overhead_excluding_hidden_materialize_ms_per_request: {latest['segment_overhead_excluding_hidden_materialize_ms_per_request']}",
        f"- segment_overhead_excluding_measured_gaps_ms_per_request: {latest['segment_overhead_excluding_measured_gaps_ms_per_request']}",
        f"- final_logits_run_ms_per_request: {latest['final_logits_run_ms_per_request']}",
        f"- final_logits_excess_ms_per_request_if_hidden_speed: {latest['final_logits_excess_ms_per_request_if_hidden_speed']}",
        f"- group_load_to_switch_gap_ratio: {latest['group_load_to_switch_gap_ratio']}",
        f"- final_excess_to_switch_gap_ratio: {latest['final_excess_to_switch_gap_ratio']}",
        "",
        "## Latest Gap Instrumented Summary",
        "",
    ]
    if latest_gap:
        lines.extend(
            [
                f"- latest_gap_file: {Path(latest_gap['file']).name}",
                f"- microbatch_count: {latest_gap['microbatch_count']}",
                f"- processed_request_count: {latest_gap['processed_request_count']}",
                f"- avg_bpu_loading: {latest_gap['avg_bpu_loading']}",
                f"- avg_nonzero_bpu_loading: {latest_gap['avg_nonzero_bpu_loading']}",
                f"- ms_per_request: {latest_gap['ms_per_request']}",
                f"- inter_segment_first_run_gap_ms_per_request: {latest_gap['inter_segment_first_run_gap_ms_per_request']}",
                f"- intra_segment_run_gap_ms_per_request: {latest_gap['intra_segment_run_gap_ms_per_request']}",
                f"- segment_overhead_excluding_measured_gaps_ms_per_request: {latest_gap['segment_overhead_excluding_measured_gaps_ms_per_request']}",
                f"- final_logits_excess_ms_per_request_if_hidden_speed: {latest_gap['final_logits_excess_ms_per_request_if_hidden_speed']}",
                "",
            ]
        )
    else:
        lines.extend(["- gap_fields_present: false", ""])
    lines.extend(
        [
        "## Latest Default Groups",
        "",
        "| group | loaded | final | load_ms/request | release_ms/request | segment_overhead_ms | hidden_materialize_ms | inter_gap_ms | intra_gap_ms | residual_after_gaps_ms | accounted_ms/request |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for group in payload["latest_default_run"]["groups"]:
        lines.append(
            f"| {group['group']} | {group['loaded_count']} | {group['contains_final_logits']} | "
            f"{group['group_load_ms_per_request']} | {group['group_release_ms_per_request']} | "
            f"{group['segment_overhead_ms']} | {group['hidden_materialize_ms']} | "
            f"{group['inter_segment_first_run_gap_ms']} | {group['intra_segment_run_gap_ms']} | "
            f"{group['segment_overhead_excluding_measured_gaps_ms']} | "
            f"{group['accounted_ms_per_request']} |"
        )

    lines.extend(
        [
            "",
            "## Run Matrix",
            "",
            "| file | groups | microbatches | avg_bpu | nonzero_bpu | ms/request | load_ms/request | switch_gap_ms/request | inter_gap_ms/request | intra_gap_ms/request | residual_after_gaps_ms/request | final_excess_ms/request |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for run in payload["runs"]:
        lines.append(
            f"| {Path(run['file']).name} | {run['group_count']} | {run['microbatch_count']} | "
            f"{run['avg_bpu_loading']} | {run['avg_nonzero_bpu_loading']} | {run['ms_per_request']} | "
            f"{run['group_load_ms_per_request']} | {run['group_switch_gap_ms_per_request']} | "
            f"{run['inter_segment_first_run_gap_ms_per_request']} | "
            f"{run['intra_segment_run_gap_ms_per_request']} | "
            f"{run['segment_overhead_excluding_measured_gaps_ms_per_request']} | "
            f"{run['final_logits_excess_ms_per_request_if_hidden_speed']} |"
        )

    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- group_release_and_unaccounted_gap_not_primary: {decision['group_release_and_unaccounted_gap_not_primary']}",
            f"- hbm_group_load_is_fixed_amortization_not_active_bpu_fix: {decision['hbm_group_load_is_fixed_amortization_not_active_bpu_fix']}",
            f"- segment_overhead_has_some_python_headroom_but_less_than_final_logits: {decision['segment_overhead_has_some_python_headroom_but_less_than_final_logits']}",
            f"- next_runtime_candidate: {decision['next_runtime_candidate']}",
            f"- scheduler_followup: {decision['scheduler_followup']}",
            "",
            "## Interpretation",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["interpretation"])
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Quantify B=4 group load/release and Python-side switch gaps.")
    parser.add_argument("--telemetry-dir", type=Path, default=Path("tmp/remote_true_batch_reports"))
    parser.add_argument("--telemetry-glob", default="b4_*true_batch_group_major_telemetry.json")
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/b4_runtime_schedule_analysis_20260619"))
    parser.add_argument("--out-stem", default="dream7b_b4_group_switch_accounting_20260619")
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
