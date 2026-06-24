#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def round_or_none(value: float | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def delta(newer: dict[str, Any], older: dict[str, Any], key: str, digits: int = 3) -> float:
    return round(as_float(newer.get(key)) - as_float(older.get(key)), digits)


def ratio(newer: dict[str, Any], older: dict[str, Any], key: str, digits: int = 4) -> float | None:
    base = as_float(older.get(key))
    if base == 0:
        return None
    return round(as_float(newer.get(key)) / base, digits)


def scaling_rows(schedule: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (schedule.get("comparisons") or {}).get("segment_major_5_group_scaling") or []
    return sorted(rows, key=lambda row: int(row.get("microbatch_count") or 0))


def build_interval_deltas(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    intervals: list[dict[str, Any]] = []
    for older, newer in zip(rows, rows[1:]):
        intervals.append(
            {
                "microbatch_count_from_to": [
                    int(older.get("microbatch_count") or 0),
                    int(newer.get("microbatch_count") or 0),
                ],
                "processed_request_count_from_to": [
                    int(older.get("processed_request_count") or 0),
                    int(newer.get("processed_request_count") or 0),
                ],
                "avg_bpu_delta": delta(newer, older, "avg_bpu_loading"),
                "nonzero_bpu_delta": delta(newer, older, "avg_nonzero_bpu_loading"),
                "ms_per_request_delta": delta(newer, older, "ms_per_request"),
                "ms_per_request_ratio": ratio(newer, older, "ms_per_request"),
                "group_load_fraction_delta": delta(newer, older, "group_load_fraction_of_wall", 6),
                "group_load_fraction_ratio": ratio(newer, older, "group_load_fraction_of_wall"),
                "required_nonzero_for_93_delta": delta(newer, older, "required_nonzero_bpu_for_93_avg"),
            }
        )
    return intervals


def summarize_asymptotic(asymptotic: dict[str, Any]) -> dict[str, Any]:
    scenarios = asymptotic.get("scenarios") or []
    latest_nonzero = as_float(asymptotic.get("latest_nonzero_bpu"))
    projected = [
        row
        for row in scenarios
        if int(row.get("microbatch_count") or 0) in {6144, 8192, 12288}
    ]
    projected_max = max(
        (as_float(row.get("avg_bpu_if_nonzero_stays_latest")) for row in projected),
        default=0.0,
    )
    return {
        "source_latest": asymptotic.get("source_latest"),
        "latest_nonzero_bpu": asymptotic.get("latest_nonzero_bpu"),
        "required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction": asymptotic.get(
            "required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction"
        ),
        "latest_nonzero_gap_to_low_load_requirement": round_or_none(
            latest_nonzero
            - as_float(
                asymptotic.get("required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction")
            )
        ),
        "projected_scenarios": projected,
        "projected_max_avg_bpu_if_nonzero_unchanged": round(projected_max, 3),
        "projected_max_still_below_93": projected_max < 93.0,
    }


def build_payload(schedule_path: Path) -> dict[str, Any]:
    schedule = read_json(schedule_path)
    rows = scaling_rows(schedule)
    if not rows:
        raise SystemExit("no segment-major 5-group scaling rows found")
    latest = rows[-1]
    comparisons = schedule.get("comparisons") or {}
    latest_gap = comparisons.get("latest_b4_vs_queue_baseline") or {}
    asymptotic = summarize_asymptotic(schedule.get("asymptotic_projection") or {})
    required_nonzero_latest = as_float(latest.get("required_nonzero_bpu_for_93_avg"))

    decision = {
        "microbatch_only_sweeps_deprioritized": True,
        "next_runtime_candidate": "seg27_28_last_token_logits",
        "do_not_run_mb6144_until_final_logits_candidate_or_active_bpu_path_changes": True,
        "reason": (
            "mb4096 still trails queue BPU and the 6144/8192/12288 projections remain "
            "below 93 avg BPU when active/nonzero BPU is held at the latest observed value."
        ),
    }

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_scaling_saturation_analysis",
        "source_paths": {"schedule": str(schedule_path)},
        "latest_observed": {
            "microbatch_count": latest.get("microbatch_count"),
            "processed_request_count": latest.get("processed_request_count"),
            "avg_bpu_loading": latest.get("avg_bpu_loading"),
            "avg_nonzero_bpu_loading": latest.get("avg_nonzero_bpu_loading"),
            "ms_per_request": latest.get("ms_per_request"),
            "group_load_fraction_of_wall": latest.get("group_load_fraction_of_wall"),
            "required_nonzero_bpu_for_93_avg": latest.get("required_nonzero_bpu_for_93_avg"),
            "avg_bpu_gap_points_vs_queue": latest_gap.get("avg_bpu_gap_points"),
            "nonzero_bpu_gap_points_vs_queue": latest_gap.get("nonzero_bpu_gap_points"),
            "latest_required_nonzero_gap_to_observed_nonzero": round_or_none(
                as_float(latest.get("avg_nonzero_bpu_loading")) - required_nonzero_latest
            ),
        },
        "scaling_rows": rows,
        "interval_deltas": build_interval_deltas(rows),
        "asymptotic_projection": asymptotic,
        "decision": decision,
        "interpretation": [
            "Microbatch scaling continues to improve average BPU mostly by amortizing fixed group load.",
            "The latest nonzero BPU is effectively flat against earlier long runs, so active compute intensity is the limiting path.",
            "More long microbatch-only sweeps should wait until the final-logits candidate or another active-BPU lever changes the runtime profile.",
        ],
    }


def write_markdown(payload: dict[str, Any], out_md: Path) -> None:
    latest = payload["latest_observed"]
    asymptotic = payload["asymptotic_projection"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B4 Scaling Saturation Analysis",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        "",
        "## Latest Observed",
        "",
        f"- microbatch_count: {latest['microbatch_count']}",
        f"- processed_request_count: {latest['processed_request_count']}",
        f"- avg_bpu_loading: {latest['avg_bpu_loading']}",
        f"- avg_nonzero_bpu_loading: {latest['avg_nonzero_bpu_loading']}",
        f"- ms_per_request: {latest['ms_per_request']}",
        f"- group_load_fraction_of_wall: {latest['group_load_fraction_of_wall']}",
        f"- required_nonzero_bpu_for_93_avg: {latest['required_nonzero_bpu_for_93_avg']}",
        f"- latest_required_nonzero_gap_to_observed_nonzero: {latest['latest_required_nonzero_gap_to_observed_nonzero']}",
        f"- avg_bpu_gap_points_vs_queue: {latest['avg_bpu_gap_points_vs_queue']}",
        f"- nonzero_bpu_gap_points_vs_queue: {latest['nonzero_bpu_gap_points_vs_queue']}",
        "",
        "## Interval Deltas",
        "",
        "| microbatches | avg_bpu_delta | nonzero_bpu_delta | ms/request_delta | ms/request_ratio | load_fraction_delta | required_nonzero_delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["interval_deltas"]:
        mb_from, mb_to = row["microbatch_count_from_to"]
        lines.append(
            f"| {mb_from}->{mb_to} | {row['avg_bpu_delta']} | {row['nonzero_bpu_delta']} | "
            f"{row['ms_per_request_delta']} | {row['ms_per_request_ratio']} | "
            f"{row['group_load_fraction_delta']} | {row['required_nonzero_for_93_delta']} |"
        )

    lines.extend(
        [
            "",
            "## Projection Gate",
            "",
            f"- latest_nonzero_bpu: {asymptotic['latest_nonzero_bpu']}",
            f"- required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction: {asymptotic['required_nonzero_bpu_for_93_avg_at_5pct_zero_or_load_fraction']}",
            f"- latest_nonzero_gap_to_low_load_requirement: {asymptotic['latest_nonzero_gap_to_low_load_requirement']}",
            f"- projected_max_avg_bpu_if_nonzero_unchanged: {asymptotic['projected_max_avg_bpu_if_nonzero_unchanged']}",
            f"- projected_max_still_below_93: {asymptotic['projected_max_still_below_93']}",
            "",
            "| microbatches | requests | projected_load_fraction | projected_avg_bpu_if_nonzero_unchanged | projected_ms/request |",
            "| ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in asymptotic["projected_scenarios"]:
        lines.append(
            f"| {row['microbatch_count']} | {row['processed_request_count']} | "
            f"{row['load_fraction_if_only_load_plus_runtime_run']} | "
            f"{row['avg_bpu_if_nonzero_stays_latest']} | "
            f"{row['ms_per_request_if_only_load_plus_runtime_run']} |"
        )

    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- microbatch_only_sweeps_deprioritized: {decision['microbatch_only_sweeps_deprioritized']}",
            f"- next_runtime_candidate: {decision['next_runtime_candidate']}",
            f"- do_not_run_mb6144_until_final_logits_candidate_or_active_bpu_path_changes: {decision['do_not_run_mb6144_until_final_logits_candidate_or_active_bpu_path_changes']}",
            f"- reason: {decision['reason']}",
            "",
            "## Interpretation",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["interpretation"])
    lines.extend(["", "## Source Paths", ""])
    lines.extend(f"- {key}: {value}" for key, value in payload["source_paths"].items())
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schedule-json",
        type=Path,
        default=Path("tmp/b4_runtime_schedule_analysis_20260619/dream7b_true_batch_b4_schedule_analysis_current.json"),
    )
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/b4_runtime_schedule_analysis_20260619"))
    parser.add_argument("--out-stem", default="dream7b_b4_scaling_saturation_analysis_20260619")
    args = parser.parse_args()

    payload = build_payload(args.schedule_json)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.out_dir / f"{args.out_stem}.json"
    out_md = args.out_dir / f"{args.out_stem}.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload, out_md)
    print(out_json)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
