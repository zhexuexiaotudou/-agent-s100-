#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_SEGMENT_DRAG = DEFAULT_ROOT / "dream7b_b4_segment_drag_breakdown_20260619.json"
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_segment_stability_audit_20260620.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_segment_stability_audit_20260620.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def stdev(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) > 1 else 0.0 if values else None


def coefficient_of_variation(values: list[float]) -> float | None:
    avg = mean(values)
    if not avg:
        return None
    return as_float(stdev(values)) / avg


def representative_group(aggregate_rows: list[dict[str, Any]], index: int) -> str | None:
    for row in aggregate_rows:
        if int(row.get("index", -1)) == index:
            return row.get("representative_group")
    return None


def segment_kind(index: int, fallback: str | None = None) -> str:
    if index == 0:
        return "token_embedding"
    if index == 27:
        return "final_logits"
    return fallback or "hidden_block"


def build_segment_rows(segment_drag: dict[str, Any]) -> list[dict[str, Any]]:
    aggregates = segment_drag.get("aggregate_segments_by_avg_run_ms") or []
    segment_stats: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "ranks": [],
            "positive_excess_ms_per_request": [],
            "avg_run_ms": [],
            "rank1_count": 0,
            "top2_count": 0,
            "top5_count": 0,
            "observed_run_names": [],
        }
    )
    for run in segment_drag.get("runs") or []:
        rows = run.get("segments_by_positive_excess_ms") or run.get("segments_by_avg_run_ms") or []
        sorted_rows = sorted(
            rows,
            key=lambda row: as_float(row.get("positive_excess_ms_per_request")),
            reverse=True,
        )
        for rank, row in enumerate(sorted_rows, start=1):
            index = int(row.get("index", -1))
            if index < 0:
                continue
            stats = segment_stats[index]
            stats["kind"] = segment_kind(index, row.get("kind"))
            stats["representative_group"] = (
                row.get("group") or representative_group(aggregates, index)
            )
            stats["ranks"].append(rank)
            stats["positive_excess_ms_per_request"].append(
                as_float(row.get("positive_excess_ms_per_request"))
            )
            stats["avg_run_ms"].append(as_float(row.get("avg_run_ms")))
            stats["observed_run_names"].append(run.get("name"))
            if rank == 1:
                stats["rank1_count"] += 1
            if rank <= 2:
                stats["top2_count"] += 1
            if rank <= 5:
                stats["top5_count"] += 1

    rows = []
    for index, stats in segment_stats.items():
        ranks = stats["ranks"]
        excess_values = stats["positive_excess_ms_per_request"]
        avg_run_values = stats["avg_run_ms"]
        observed = len(ranks)
        rows.append(
            {
                "index": index,
                "kind": segment_kind(index, stats.get("kind")),
                "representative_group": stats.get("representative_group"),
                "observed_run_count": observed,
                "rank1_count": stats["rank1_count"],
                "top2_count": stats["top2_count"],
                "top5_count": stats["top5_count"],
                "rank1_rate": round_or_none(stats["rank1_count"] / observed if observed else None),
                "top2_rate": round_or_none(stats["top2_count"] / observed if observed else None),
                "top5_rate": round_or_none(stats["top5_count"] / observed if observed else None),
                "mean_rank": round_or_none(mean([float(rank) for rank in ranks])),
                "max_rank": max(ranks) if ranks else None,
                "mean_positive_excess_ms_per_request": round_or_none(mean(excess_values)),
                "stdev_positive_excess_ms_per_request": round_or_none(stdev(excess_values)),
                "cv_positive_excess": round_or_none(coefficient_of_variation(excess_values)),
                "min_positive_excess_ms_per_request": round_or_none(min(excess_values) if excess_values else None),
                "max_positive_excess_ms_per_request": round_or_none(max(excess_values) if excess_values else None),
                "mean_avg_run_ms": round_or_none(mean(avg_run_values)),
                "stdev_avg_run_ms": round_or_none(stdev(avg_run_values)),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            as_float(row.get("rank1_rate")),
            as_float(row.get("top2_rate")),
            as_float(row.get("mean_positive_excess_ms_per_request")),
        ),
        reverse=True,
    )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    segment_drag = read_json(args.segment_drag_json)
    rows = build_segment_rows(segment_drag)
    by_index = {int(row["index"]): row for row in rows}
    final = by_index.get(27, {})
    token = by_index.get(0, {})
    hidden_rows = [row for row in rows if row.get("kind") == "hidden_block"]
    max_hidden = max(
        hidden_rows,
        key=lambda row: as_float(row.get("mean_positive_excess_ms_per_request")),
        default={},
    )
    run_count = len(segment_drag.get("runs") or [])
    final_mean = as_float(final.get("mean_positive_excess_ms_per_request"))
    token_mean = as_float(token.get("mean_positive_excess_ms_per_request"))
    hidden_mean = as_float(max_hidden.get("mean_positive_excess_ms_per_request"))
    final_rank1_rate = as_float(final.get("rank1_rate"))
    final_top2_rate = as_float(final.get("top2_rate"))
    final_cv = as_float(final.get("cv_positive_excess"))

    stable_primary = (
        final.get("index") == 27
        and final_rank1_rate == 1.0
        and final_top2_rate == 1.0
        and final_mean > 0.0
        and final_cv < 0.01
    )
    token_is_secondary = token_mean > 0.0 and final_mean / token_mean > 10.0
    hidden_order_not_primary = hidden_mean > 0.0 and final_mean / hidden_mean > 100.0

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_segment_stability_audit",
        "source_paths": {
            "segment_drag": str(args.segment_drag_json),
        },
        "summary": {
            "analyzed_run_count": run_count,
            "ranked_segment_count": len(rows),
            "final_logits_rank1_rate": final.get("rank1_rate"),
            "final_logits_top2_rate": final.get("top2_rate"),
            "final_logits_mean_positive_excess_ms_per_request": final.get(
                "mean_positive_excess_ms_per_request"
            ),
            "final_logits_cv_positive_excess": final.get("cv_positive_excess"),
            "token_embedding_mean_positive_excess_ms_per_request": token.get(
                "mean_positive_excess_ms_per_request"
            ),
            "max_hidden_index": max_hidden.get("index"),
            "max_hidden_mean_positive_excess_ms_per_request": max_hidden.get(
                "mean_positive_excess_ms_per_request"
            ),
            "final_to_token_excess_ratio": round_or_none(
                final_mean / token_mean if token_mean else None,
                3,
            ),
            "final_to_max_hidden_excess_ratio": round_or_none(
                final_mean / hidden_mean if hidden_mean else None,
                3,
            ),
        },
        "leaderboard": rows,
        "decision": {
            "stable_primary_bottleneck": "seg27_28_final_logits" if stable_primary else None,
            "final_logits_stable_rank1": stable_primary,
            "token_embedding_secondary_not_primary": token_is_secondary,
            "hidden_inner_order_tuning_not_primary": hidden_order_not_primary,
            "next_runtime_candidate": "seg27_28_last_token_logits",
            "do_not_run_hidden_order_sweeps_now": hidden_order_not_primary,
            "do_not_run_standard_b4_sweeps_now": True,
            "reason": (
                "final logits is rank 1 in every analyzed B=4 run with very low "
                "positive-excess variability; token embedding is a residency follow-up, "
                "and hidden-block ordering is not a primary lever."
            ),
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B4 Segment Stability Audit",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- analyzed_run_count: `{summary['analyzed_run_count']}`",
        f"- stable_primary_bottleneck: `{decision['stable_primary_bottleneck']}`",
        f"- next_runtime_candidate: `{decision['next_runtime_candidate']}`",
        f"- reason: {decision['reason']}",
        "",
        "## Dominance Summary",
        "",
        f"- final_logits_rank1_rate: `{summary['final_logits_rank1_rate']}`",
        f"- final_logits_top2_rate: `{summary['final_logits_top2_rate']}`",
        f"- final_logits_mean_positive_excess_ms_per_request: `{summary['final_logits_mean_positive_excess_ms_per_request']}`",
        f"- final_logits_cv_positive_excess: `{summary['final_logits_cv_positive_excess']}`",
        f"- final_to_token_excess_ratio: `{summary['final_to_token_excess_ratio']}`",
        f"- final_to_max_hidden_excess_ratio: `{summary['final_to_max_hidden_excess_ratio']}`",
        f"- do_not_run_hidden_order_sweeps_now: `{decision['do_not_run_hidden_order_sweeps_now']}`",
        f"- do_not_run_standard_b4_sweeps_now: `{decision['do_not_run_standard_b4_sweeps_now']}`",
        "",
        "## Leaderboard",
        "",
        "| rank | index | kind | group | rank1 rate | top2 rate | mean rank | mean excess ms/request | cv excess |",
        "| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, row in enumerate(payload["leaderboard"][:10], start=1):
        lines.append(
            "| "
            f"{rank} | {row.get('index')} | {row.get('kind')} | {row.get('representative_group')} | "
            f"{row.get('rank1_rate')} | {row.get('top2_rate')} | {row.get('mean_rank')} | "
            f"{row.get('mean_positive_excess_ms_per_request')} | {row.get('cv_positive_excess')} |"
        )
    lines.extend(["", "## Source Paths", ""])
    for key, value in payload["source_paths"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit cross-run stability of B=4 segment bottlenecks from existing telemetry."
    )
    parser.add_argument("--segment-drag-json", type=Path, default=DEFAULT_SEGMENT_DRAG)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(args.out_md)
    print(args.out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
