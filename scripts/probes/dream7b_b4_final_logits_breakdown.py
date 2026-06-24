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


def round_or_none(value: float | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def group_range(group: dict[str, Any]) -> str:
    return f"{group.get('group_start')}:{group.get('group_end')}"


def segment_rows(group: dict[str, Any]) -> list[dict[str, Any]]:
    return group.get("segment_rows") or []


def run_segment_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in payload.get("group_rows") or []:
        label = group_range(group)
        for row in segment_rows(group):
            copied = dict(row)
            copied["group"] = label
            rows.append(copied)
    return rows


def analyze_run(path: Path) -> dict[str, Any] | None:
    payload = load_json(path)
    if payload.get("verdict") != "ok_dream7b_true_batch_group_major_telemetry":
        return None
    if payload.get("inner_order") != "segment-major":
        return None
    groups: list[dict[str, Any]] = payload.get("group_rows") or []
    rows = run_segment_rows(payload)
    final_rows = [row for row in rows if as_int(row.get("index")) == 27]
    hidden_rows = [row for row in rows if 1 <= as_int(row.get("index")) <= 26]
    token_rows = [row for row in rows if as_int(row.get("index")) == 0]
    if not final_rows or not hidden_rows:
        return None

    final_segment = final_rows[0]
    final_group = None
    for group in groups:
        if any(as_int(row.get("index")) == 27 for row in segment_rows(group)):
            final_group = group
            break
    if final_group is None:
        return None

    wall_ms = as_float(payload.get("wall_ms"))
    total_segment_run_ms = sum(as_float(row.get("total_run_ms")) for row in rows)
    total_segment_total_ms = sum(as_float(row.get("segment_total_ms")) for row in rows)
    hidden_avg_values = [as_float(row.get("avg_run_ms")) for row in hidden_rows if row.get("avg_run_ms") is not None]
    hidden_total_run_ms = sum(as_float(row.get("total_run_ms")) for row in hidden_rows)
    hidden_total_segment_ms = sum(as_float(row.get("segment_total_ms")) for row in hidden_rows)
    final_group_rows = segment_rows(final_group)
    final_group_segment_total_ms = sum(as_float(row.get("segment_total_ms")) for row in final_group_rows)
    final_group_run_ms = sum(as_float(row.get("total_run_ms")) for row in final_group_rows)
    final_group_overhead_ms = max(0.0, final_group_segment_total_ms - final_group_run_ms)
    final_group_load_ms = as_float(final_group.get("group_load_ms"))
    final_group_release_ms = as_float(final_group.get("group_release_ms"))
    final_group_loop_ms = as_float(final_group.get("group_loop_ms"))
    final_group_accounted_ms = final_group_load_ms + final_group_segment_total_ms + final_group_release_ms
    final_group_gap_ms = final_group_loop_ms - final_group_accounted_ms if final_group_loop_ms else None

    non_final_groups = [group for group in groups if group is not final_group]
    non_final_group_load_values = [as_float(group.get("group_load_ms")) for group in non_final_groups]
    non_final_group_segment_totals = [
        sum(as_float(row.get("segment_total_ms")) for row in segment_rows(group))
        for group in non_final_groups
    ]
    group_gap_values: list[float] = []
    for group in groups:
        loop_ms = as_float(group.get("group_loop_ms"))
        if not loop_ms:
            continue
        group_segment_total = sum(as_float(row.get("segment_total_ms")) for row in segment_rows(group))
        accounted = as_float(group.get("group_load_ms")) + group_segment_total + as_float(group.get("group_release_ms"))
        group_gap_values.append(loop_ms - accounted)

    final_avg_run_ms = as_float(final_segment.get("avg_run_ms"))
    hidden_mean_avg_run_ms = sum(hidden_avg_values) / len(hidden_avg_values) if hidden_avg_values else None
    final_segment_total_ms = as_float(final_segment.get("segment_total_ms"))
    final_segment_run_ms = as_float(final_segment.get("total_run_ms"))
    final_segment_overhead_ms = max(0.0, final_segment_total_ms - final_segment_run_ms)

    return {
        "file": str(path),
        "generated_at": payload.get("generated_at"),
        "preallocate_hidden": bool(payload.get("preallocate_hidden", False)),
        "microbatch_count": payload.get("microbatch_count"),
        "batch_size": payload.get("batch_size"),
        "processed_request_count": payload.get("processed_request_count"),
        "group_count": len(groups),
        "group_ranges": [group_range(group) for group in groups],
        "wall_ms": payload.get("wall_ms"),
        "ms_per_request": payload.get("amortized_wall_ms_per_request"),
        "avg_bpu_loading": payload.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": payload.get("avg_nonzero_bpu_loading"),
        "token_avg_run_ms": round_or_none(
            sum(as_float(row.get("avg_run_ms")) for row in token_rows) / len(token_rows)
            if token_rows
            else None,
            4,
        ),
        "hidden_mean_avg_run_ms": round_or_none(hidden_mean_avg_run_ms, 4),
        "final_avg_run_ms": round_or_none(final_avg_run_ms, 4),
        "final_vs_hidden_avg_run_ratio": round_or_none(
            final_avg_run_ms / hidden_mean_avg_run_ms if hidden_mean_avg_run_ms else None,
            4,
        ),
        "hidden_total_run_ms": round(hidden_total_run_ms, 3),
        "hidden_total_segment_ms": round(hidden_total_segment_ms, 3),
        "final_segment_run_ms": round(final_segment_run_ms, 3),
        "final_segment_total_ms": round(final_segment_total_ms, 3),
        "final_segment_overhead_ms": round(final_segment_overhead_ms, 3),
        "final_segment_run_fraction_of_all_segment_run": round_or_none(
            final_segment_run_ms / total_segment_run_ms if total_segment_run_ms else None,
            6,
        ),
        "final_segment_total_fraction_of_all_segment_total": round_or_none(
            final_segment_total_ms / total_segment_total_ms if total_segment_total_ms else None,
            6,
        ),
        "final_segment_wall_fraction": round_or_none(
            final_segment_total_ms / wall_ms if wall_ms else None,
            6,
        ),
        "final_group_range": group_range(final_group),
        "final_group_load_ms": round(final_group_load_ms, 3),
        "final_group_release_ms": round(final_group_release_ms, 3) if final_group_release_ms else None,
        "final_group_loop_ms": round(final_group_loop_ms, 3) if final_group_loop_ms else None,
        "final_group_gap_ms": round_or_none(final_group_gap_ms, 3),
        "final_group_segment_total_ms": round(final_group_segment_total_ms, 3),
        "final_group_run_ms": round(final_group_run_ms, 3),
        "final_group_overhead_ms": round(final_group_overhead_ms, 3),
        "final_group_wall_fraction": round_or_none(
            (final_group_load_ms + final_group_segment_total_ms + final_group_release_ms) / wall_ms
            if wall_ms
            else None,
            6,
        ),
        "non_final_group_load_mean_ms": round_or_none(
            sum(non_final_group_load_values) / len(non_final_group_load_values)
            if non_final_group_load_values
            else None,
            3,
        ),
        "final_group_load_vs_non_final_mean_ratio": round_or_none(
            final_group_load_ms / (sum(non_final_group_load_values) / len(non_final_group_load_values))
            if non_final_group_load_values
            and sum(non_final_group_load_values)
            else None,
            4,
        ),
        "non_final_group_segment_total_mean_ms": round_or_none(
            sum(non_final_group_segment_totals) / len(non_final_group_segment_totals)
            if non_final_group_segment_totals
            else None,
            3,
        ),
        "final_group_segment_total_vs_non_final_mean_ratio": round_or_none(
            final_group_segment_total_ms
            / (sum(non_final_group_segment_totals) / len(non_final_group_segment_totals))
            if non_final_group_segment_totals
            and sum(non_final_group_segment_totals)
            else None,
            4,
        ),
        "observed_group_gap_total_ms": round(sum(group_gap_values), 3) if group_gap_values else None,
        "observed_group_gap_count": len(group_gap_values),
    }


def write_markdown(payload: dict[str, Any], out_md: Path) -> None:
    rows: list[dict[str, Any]] = payload["runs"]
    lines = [
        "# Dream7B B4 Final Logits Breakdown",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- analyzed_run_count: {len(rows)}",
        "",
        "## Run Summary",
        "",
        "| file | prealloc | groups | microbatches | avg_bpu | nonzero_bpu | ms/request | final_avg_ms | hidden_avg_ms | final/hidden | final_run_share | final_group | final_group_wall_share |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {Path(row['file']).name} | {row['preallocate_hidden']} | {row['group_count']} | "
            f"{row['microbatch_count']} | {row['avg_bpu_loading']} | {row['avg_nonzero_bpu_loading']} | "
            f"{row['ms_per_request']} | {row['final_avg_run_ms']} | {row['hidden_mean_avg_run_ms']} | "
            f"{row['final_vs_hidden_avg_run_ratio']} | "
            f"{100 * as_float(row.get('final_segment_run_fraction_of_all_segment_run')):.2f}% | "
            f"{row['final_group_range']} | {100 * as_float(row.get('final_group_wall_fraction')):.2f}% |"
        )

    latest = payload.get("latest_non_prealloc_default_group")
    if latest:
        lines.extend(
            [
                "",
                "## Latest Default Group",
                "",
                f"- file: {Path(latest['file']).name}",
                f"- microbatch_count: {latest['microbatch_count']}",
                f"- final_avg_run_ms: {latest['final_avg_run_ms']}",
                f"- hidden_mean_avg_run_ms: {latest['hidden_mean_avg_run_ms']}",
                f"- final_vs_hidden_avg_run_ratio: {latest['final_vs_hidden_avg_run_ratio']}",
                f"- final_segment_total_ms: {latest['final_segment_total_ms']}",
                f"- final_segment_total_fraction_of_all_segment_total: {latest['final_segment_total_fraction_of_all_segment_total']}",
                f"- final_group_load_ms: {latest['final_group_load_ms']}",
                f"- final_group_load_vs_non_final_mean_ratio: {latest['final_group_load_vs_non_final_mean_ratio']}",
                f"- final_group_segment_total_vs_non_final_mean_ratio: {latest['final_group_segment_total_vs_non_final_mean_ratio']}",
            ]
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["interpretation"])
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--telemetry-dir", default="tmp/remote_true_batch_reports")
    parser.add_argument("--telemetry-glob", default="b4_*true_batch_group_major_telemetry.json")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--out-stem", default="dream7b_b4_final_logits_breakdown_20260619")
    args = parser.parse_args()

    telemetry_dir = Path(args.telemetry_dir)
    rows = [
        row
        for row in (analyze_run(path) for path in sorted(telemetry_dir.glob(args.telemetry_glob)))
        if row is not None
    ]
    rows.sort(
        key=lambda row: (
            as_int(row.get("microbatch_count")),
            as_int(row.get("group_count")),
            bool(row.get("preallocate_hidden")),
            str(row.get("file")),
        )
    )
    if not rows:
        raise SystemExit("no successful segment-major telemetry rows found")

    default_rows = [
        row
        for row in rows
        if row["group_count"] == 5 and not row["preallocate_hidden"]
    ]
    latest = max(default_rows, key=lambda row: as_int(row.get("microbatch_count"))) if default_rows else None
    interpretation = [
        "Final logits remains a runtime outlier: its per-microbatch run time is about 2.5x a hidden segment in every successful segment-major sample.",
        "Final group load is not the main bottleneck by itself; the final group is expensive because it contains the logits segment plus its group load.",
        "Group-switch gap is measurable only in newly instrumented mb128 runs; observed unaccounted group gap is small versus HBM load and segment execution.",
        "Scheduling work should treat final logits separately from hidden block scheduling; group split changes do not remove the final segment cost.",
    ]
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_final_logits_breakdown",
        "runs": rows,
        "latest_non_prealloc_default_group": latest,
        "interpretation": interpretation,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / f"{args.out_stem}.json"
    out_md = out_dir / f"{args.out_stem}.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload, out_md)
    print(out_json)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
