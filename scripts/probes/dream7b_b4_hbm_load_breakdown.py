#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
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


def segment_kind(index: int) -> str:
    if index == 0:
        return "token_embedding"
    if index == 27:
        return "final_logits"
    return "hidden_block"


def group_label(group: dict[str, Any]) -> str:
    return f"{group.get('group_start')}:{group.get('group_end')}"


def is_usable_payload(payload: dict[str, Any]) -> bool:
    if payload.get("verdict") != "ok_dream7b_true_batch_group_major_telemetry":
        return False
    if payload.get("inner_order") != "segment-major":
        return False
    if bool(payload.get("preallocate_hidden", False)):
        return False
    if int(payload.get("batch_size") or 0) != 4:
        return False
    if int(payload.get("processed_request_count") or 0) <= 0:
        return False
    return any(group.get("loaded_segments") for group in payload.get("group_rows") or [])


def analyze_payload(path: Path) -> dict[str, Any] | None:
    payload = read_json(path)
    if not is_usable_payload(payload):
        return None

    groups = payload.get("group_rows") or []
    processed = as_int(payload.get("processed_request_count"))
    load_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    for group in groups:
        label = group_label(group)
        group_load_ms = as_float(group.get("group_load_ms"))
        loaded_segments = group.get("loaded_segments") or []
        group_size_mib = sum(as_float(segment.get("hbm_size_mib")) for segment in loaded_segments)
        segment_load_sum = sum(as_float(segment.get("load_ms")) for segment in loaded_segments)
        group_rows.append(
            {
                "group": label,
                "loaded_count": as_int(group.get("loaded_count")),
                "contains_final_logits": any(as_int(segment.get("index")) == 27 for segment in loaded_segments),
                "group_load_ms": round(group_load_ms, 3),
                "group_load_ms_per_request": round_or_none(group_load_ms / processed if processed else None, 6),
                "loaded_segment_load_sum_ms": round(segment_load_sum, 3),
                "unattributed_load_ms": round(group_load_ms - segment_load_sum, 3),
                "hbm_size_mib": round(group_size_mib, 3),
                "load_ms_per_mib": round_or_none(group_load_ms / group_size_mib if group_size_mib else None, 6),
            }
        )
        for segment in loaded_segments:
            index = as_int(segment.get("index"))
            load_ms = as_float(segment.get("load_ms"))
            size_mib = as_float(segment.get("hbm_size_mib"))
            load_rows.append(
                {
                    "group": label,
                    "index": index,
                    "kind": segment_kind(index),
                    "model_name": segment.get("model_name"),
                    "hbm_size_mib": round(size_mib, 3),
                    "load_ms": round(load_ms, 3),
                    "load_ms_per_request": round_or_none(load_ms / processed if processed else None, 6),
                    "load_ms_per_mib": round_or_none(load_ms / size_mib if size_mib else None, 6),
                }
            )

    hidden_loads = [row["load_ms"] for row in load_rows if row["kind"] == "hidden_block"]
    final_rows = [row for row in load_rows if row["kind"] == "final_logits"]
    token_rows = [row for row in load_rows if row["kind"] == "token_embedding"]
    total_load_ms = sum(row["load_ms"] for row in load_rows)
    return {
        "file": str(path),
        "generated_at": payload.get("generated_at"),
        "microbatch_count": as_int(payload.get("microbatch_count")),
        "processed_request_count": processed,
        "avg_bpu_loading": payload.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": payload.get("avg_nonzero_bpu_loading"),
        "ms_per_request": payload.get("amortized_wall_ms_per_request"),
        "release_gc_mode": payload.get("release_gc_mode") or "collect",
        "prewarm_hbm": bool(payload.get("prewarm_hbm", False)),
        "total_hbm_prewarm_ms": (payload.get("timing_summary") or {}).get("total_hbm_prewarm_ms"),
        "total_hbm_prewarm_mib": (payload.get("timing_summary") or {}).get("total_hbm_prewarm_mib"),
        "total_group_load_ms": round(sum(as_float(group.get("group_load_ms")) for group in groups), 3),
        "summed_segment_load_ms": round(total_load_ms, 3),
        "total_group_load_ms_per_request": round_or_none(
            sum(as_float(group.get("group_load_ms")) for group in groups) / processed if processed else None,
            6,
        ),
        "hidden_mean_load_ms": round_or_none(statistics.fmean(hidden_loads), 3) if hidden_loads else None,
        "hidden_stdev_load_ms": round_or_none(statistics.pstdev(hidden_loads), 3) if len(hidden_loads) > 1 else None,
        "token_load_ms": token_rows[0]["load_ms"] if token_rows else None,
        "final_load_ms": final_rows[0]["load_ms"] if final_rows else None,
        "final_vs_hidden_load_ratio": round_or_none(
            final_rows[0]["load_ms"] / statistics.fmean(hidden_loads)
            if final_rows and hidden_loads and statistics.fmean(hidden_loads)
            else None,
            4,
        ),
        "group_rows": group_rows,
        "segment_load_rows": sorted(load_rows, key=lambda row: row["load_ms"], reverse=True),
    }


def build_payload(paths: list[Path]) -> dict[str, Any]:
    runs = [item for path in paths if (item := analyze_payload(path)) is not None]
    runs.sort(key=lambda row: (row["microbatch_count"], str(row.get("generated_at") or "")))
    latest_default = None
    default_runs = [
        row
        for row in runs
        if row.get("release_gc_mode") == "collect"
        and not row.get("prewarm_hbm")
    ]
    if default_runs:
        latest_default = max(default_runs, key=lambda row: row["microbatch_count"])

    if latest_default:
        slowest = latest_default["segment_load_rows"][:6]
        final_vs_hidden = latest_default.get("final_vs_hidden_load_ratio")
        token_load = as_float(latest_default.get("token_load_ms"))
        final_load = as_float(latest_default.get("final_load_ms"))
        hidden_mean = as_float(latest_default.get("hidden_mean_load_ms"))
        final_group = next(
            (group for group in latest_default["group_rows"] if group.get("contains_final_logits")),
            {},
        )
        largest_group = max(latest_default["group_rows"], key=lambda row: as_float(row.get("group_load_ms")))
    else:
        slowest = []
        final_vs_hidden = None
        token_load = 0.0
        final_load = 0.0
        hidden_mean = 0.0
        final_group = {}
        largest_group = {}

    decision = {
        "per_segment_load_telemetry_ready": bool(runs),
        "token_embedding_load_is_outlier": bool(hidden_mean and token_load / hidden_mean > 2.0),
        "final_logits_load_is_outlier": bool(hidden_mean and final_load / hidden_mean > 2.0),
        "largest_load_group": largest_group.get("group"),
        "final_group_is_largest_load_group": bool(final_group and largest_group and final_group.get("group") == largest_group.get("group")),
        "group_boundary_tuning_alone_not_primary": True,
        "continue_prioritizing_final_logits_compute_or_output_reduction": True,
    }
    prewarm_comparison = {}
    if latest_default:
        matching_prewarm = [
            row
            for row in runs
            if row.get("prewarm_hbm")
            and row.get("release_gc_mode") == latest_default.get("release_gc_mode")
            and row.get("microbatch_count") == latest_default.get("microbatch_count")
        ]
        if matching_prewarm:
            prewarm = max(matching_prewarm, key=lambda row: str(row.get("generated_at") or ""))
            prewarm_comparison = {
                "baseline_file": latest_default.get("file"),
                "prewarm_file": prewarm.get("file"),
                "microbatch_count": prewarm.get("microbatch_count"),
                "wall_ms_per_request_delta": round(
                    as_float(prewarm.get("ms_per_request")) - as_float(latest_default.get("ms_per_request")),
                    3,
                ),
                "group_load_ms_delta": round(
                    as_float(prewarm.get("total_group_load_ms")) - as_float(latest_default.get("total_group_load_ms")),
                    3,
                ),
                "group_load_ms_per_request_delta": round(
                    as_float(prewarm.get("total_group_load_ms_per_request"))
                    - as_float(latest_default.get("total_group_load_ms_per_request")),
                    6,
                ),
                "prewarm_ms": prewarm.get("total_hbm_prewarm_ms"),
                "prewarm_mib": prewarm.get("total_hbm_prewarm_mib"),
                "net_prewarm_plus_group_load_ms_delta": round(
                    as_float(prewarm.get("total_hbm_prewarm_ms"))
                    + as_float(prewarm.get("total_group_load_ms"))
                    - as_float(latest_default.get("total_group_load_ms")),
                    3,
                ),
            }
            decision["prewarm_hbm_default"] = (
                as_float(prewarm_comparison.get("wall_ms_per_request_delta")) < 0
                and as_float(prewarm_comparison.get("net_prewarm_plus_group_load_ms_delta")) < 0
            )
    decision.setdefault("prewarm_hbm_default", False)
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_hbm_load_breakdown" if runs else "no_load_segment_telemetry",
        "analyzed_run_count": len(runs),
        "latest_default_run": latest_default,
        "slowest_load_segments_latest": slowest,
        "decision": decision,
        "prewarm_comparison": prewarm_comparison,
        "runs": runs,
        "interpretation": [
            "Per-segment HBM load timing is now captured directly by the telemetry probe.",
            "Use this report to separate HBM load placement from segment runtime cost.",
            "If final logits is not a load-time outlier, optimize final logits compute/output before more HBM group-boundary sweeps.",
        ],
    }


def render_md(payload: dict[str, Any], out_md: Path) -> None:
    latest = payload.get("latest_default_run") or {}
    decision = payload.get("decision") or {}
    lines = [
        "# Dream7B B4 HBM Load Breakdown",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- analyzed_run_count: {payload['analyzed_run_count']}",
        "",
        "## Latest Default Run",
        "",
        f"- file: {Path(str(latest.get('file') or '')).name}",
        f"- microbatch_count: {latest.get('microbatch_count')}",
        f"- total_group_load_ms_per_request: {latest.get('total_group_load_ms_per_request')}",
        f"- hidden_mean_load_ms: {latest.get('hidden_mean_load_ms')}",
        f"- hidden_stdev_load_ms: {latest.get('hidden_stdev_load_ms')}",
        f"- token_load_ms: {latest.get('token_load_ms')}",
        f"- final_load_ms: {latest.get('final_load_ms')}",
        f"- final_vs_hidden_load_ratio: {latest.get('final_vs_hidden_load_ratio')}",
        f"- prewarm_hbm: {latest.get('prewarm_hbm')}",
        "",
        "## Slowest Loaded Segments",
        "",
        "| rank | group | segment | kind | load_ms | size_mib | load_ms_per_mib |",
        "| ---: | --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for rank, row in enumerate(payload.get("slowest_load_segments_latest") or [], start=1):
        lines.append(
            f"| {rank} | {row['group']} | {row['index']} | {row['kind']} | "
            f"{row['load_ms']} | {row['hbm_size_mib']} | {row['load_ms_per_mib']} |"
        )

    lines.extend(
        [
            "",
            "## Group Load",
            "",
            "| group | loaded | final | load_ms/request | size_mib | load_ms_per_mib | unattributed_load_ms |",
            "| --- | ---: | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in latest.get("group_rows") or []:
        lines.append(
            f"| {row['group']} | {row['loaded_count']} | {row['contains_final_logits']} | "
            f"{row['group_load_ms_per_request']} | {row['hbm_size_mib']} | "
            f"{row['load_ms_per_mib']} | {row['unattributed_load_ms']} |"
        )

    prewarm = payload.get("prewarm_comparison") or {}
    if prewarm:
        lines.extend(
            [
                "",
                "## HBM Prewarm Comparison",
                "",
                f"- baseline_file: {Path(str(prewarm.get('baseline_file') or '')).name}",
                f"- prewarm_file: {Path(str(prewarm.get('prewarm_file') or '')).name}",
                f"- microbatch_count: {prewarm.get('microbatch_count')}",
                f"- wall_ms_per_request_delta: {prewarm.get('wall_ms_per_request_delta')}",
                f"- group_load_ms_delta: {prewarm.get('group_load_ms_delta')}",
                f"- group_load_ms_per_request_delta: {prewarm.get('group_load_ms_per_request_delta')}",
                f"- prewarm_ms: {prewarm.get('prewarm_ms')}",
                f"- prewarm_mib: {prewarm.get('prewarm_mib')}",
                f"- net_prewarm_plus_group_load_ms_delta: {prewarm.get('net_prewarm_plus_group_load_ms_delta')}",
            ]
        )

    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- per_segment_load_telemetry_ready: {decision.get('per_segment_load_telemetry_ready')}",
            f"- token_embedding_load_is_outlier: {decision.get('token_embedding_load_is_outlier')}",
            f"- final_logits_load_is_outlier: {decision.get('final_logits_load_is_outlier')}",
            f"- largest_load_group: {decision.get('largest_load_group')}",
            f"- final_group_is_largest_load_group: {decision.get('final_group_is_largest_load_group')}",
            f"- group_boundary_tuning_alone_not_primary: {decision.get('group_boundary_tuning_alone_not_primary')}",
            f"- continue_prioritizing_final_logits_compute_or_output_reduction: {decision.get('continue_prioritizing_final_logits_compute_or_output_reduction')}",
            f"- prewarm_hbm_default: {decision.get('prewarm_hbm_default')}",
            "",
            "## Interpretation",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload.get("interpretation") or [])
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze per-segment HBM load timing for Dream7B B=4 telemetry.")
    parser.add_argument("--telemetry-dir", type=Path, default=Path("tmp/remote_true_batch_reports"))
    parser.add_argument("--telemetry-glob", default="b4_*true_batch_group_major_telemetry.json")
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/b4_runtime_schedule_analysis_20260619"))
    parser.add_argument("--out-stem", default="dream7b_b4_hbm_load_breakdown_20260619")
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
