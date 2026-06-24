#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_TELEMETRY = Path(
    "tmp/remote_true_batch_reports/"
    "b4_mb512_segment_major_post_instrumentation_20260621_true_batch_group_major_telemetry.json"
)
DEFAULT_ANALYSIS_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_OUT_JSON = DEFAULT_ANALYSIS_ROOT / "dream7b_b4_post_instrumentation_overhead_analysis_20260621.json"
DEFAULT_OUT_MD = DEFAULT_ANALYSIS_ROOT / "dream7b_b4_post_instrumentation_overhead_analysis_20260621.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def per_request(value: Any, processed_request_count: int) -> float | None:
    if value is None or processed_request_count <= 0:
        return None
    return round(float(value) / processed_request_count, 6)


def segment_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in payload.get("group_rows") or []:
        if not isinstance(group, dict):
            continue
        group_label = f"{group.get('group_start')}:{group.get('group_end')}"
        for row in group.get("segment_rows") or []:
            if isinstance(row, dict):
                rows.append({**row, "group": group_label})
    return rows


def ranked_segments(rows: list[dict[str, Any]], key: str, processed_request_count: int) -> list[dict[str, Any]]:
    ranked = sorted(rows, key=lambda row: float(row.get(key) or 0.0), reverse=True)
    return [
        {
            "index": row.get("index"),
            "group": row.get("group"),
            "model_name": row.get("model_name"),
            key: row.get(key),
            f"{key}_per_request": per_request(row.get(key), processed_request_count),
            "avg_run_ms": row.get("avg_run_ms"),
            "output_postprocess_ms": row.get("output_postprocess_ms"),
            "hidden_materialize_ms": row.get("hidden_materialize_ms"),
            "input_prepare_ms": row.get("input_prepare_ms"),
        }
        for row in ranked[:8]
    ]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    telemetry = read_json(args.telemetry)
    timing = telemetry.get("timing_summary") or {}
    rows = segment_rows(telemetry)
    processed_request_count = int(telemetry.get("processed_request_count") or 0)
    final_row = next((row for row in rows if row.get("index") == 27), {})
    hidden_rows = [row for row in rows if row.get("index") not in (0, 27)]
    hidden_avg_run_ms = timing.get("hidden_avg_run_ms")
    final_avg_run_ms = timing.get("final_logits_avg_run_ms")
    final_excess_ms_per_request = None
    if final_avg_run_ms is not None and hidden_avg_run_ms is not None:
        # One final-logits run is executed for each microbatch. Divide by batch size
        # to compare with the request-level metrics used elsewhere in the packet.
        batch_size = int(telemetry.get("batch_size") or 1)
        final_excess_ms_per_request = round(
            (float(final_avg_run_ms) - float(hidden_avg_run_ms)) / max(1, batch_size),
            6,
        )

    totals = {
        "wall_ms": telemetry.get("wall_ms"),
        "processed_request_count": processed_request_count,
        "ms_per_request": telemetry.get("amortized_wall_ms_per_request"),
        "avg_bpu_loading": telemetry.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": telemetry.get("avg_nonzero_bpu_loading"),
        "total_input_prepare_ms": timing.get("total_input_prepare_ms"),
        "input_prepare_ms_per_request": per_request(
            timing.get("total_input_prepare_ms"), processed_request_count
        ),
        "input_prepare_fraction_of_wall": timing.get("input_prepare_fraction_of_wall"),
        "total_output_postprocess_ms": timing.get("total_output_postprocess_ms"),
        "output_postprocess_ms_per_request": per_request(
            timing.get("total_output_postprocess_ms"), processed_request_count
        ),
        "output_postprocess_fraction_of_wall": timing.get("output_postprocess_fraction_of_wall"),
        "total_hidden_materialize_ms": timing.get("total_hidden_materialize_ms"),
        "hidden_materialize_ms_per_request": per_request(
            timing.get("total_hidden_materialize_ms"), processed_request_count
        ),
        "hidden_materialize_ms_per_item": timing.get("hidden_materialize_ms_per_item"),
        "reused_hidden_buffer_count": timing.get("reused_hidden_buffer_count"),
        "total_segment_overhead_ms": timing.get("total_segment_overhead_ms"),
        "segment_overhead_ms_per_request": per_request(
            timing.get("total_segment_overhead_ms"), processed_request_count
        ),
        "estimated_unaccounted_gap_ms": timing.get("estimated_unaccounted_gap_ms"),
        "unaccounted_gap_ms_per_request": per_request(
            timing.get("estimated_unaccounted_gap_ms"), processed_request_count
        ),
        "total_intra_segment_run_gap_ms": timing.get("total_intra_segment_run_gap_ms"),
        "intra_segment_run_gap_ms_per_request": per_request(
            timing.get("total_intra_segment_run_gap_ms"), processed_request_count
        ),
        "final_logits_avg_run_ms": final_avg_run_ms,
        "hidden_avg_run_ms": hidden_avg_run_ms,
        "final_vs_hidden_avg_run_ratio": timing.get("final_vs_hidden_avg_run_ratio"),
        "final_excess_ms_per_request_vs_hidden": final_excess_ms_per_request,
        "final_output_postprocess_ms": final_row.get("output_postprocess_ms"),
        "final_output_postprocess_ms_per_request": per_request(
            final_row.get("output_postprocess_ms"), processed_request_count
        ),
        "final_input_prepare_ms": final_row.get("input_prepare_ms"),
        "final_input_prepare_ms_per_request": per_request(
            final_row.get("input_prepare_ms"), processed_request_count
        ),
        "hidden_segment_count": len(hidden_rows),
    }
    final_excess = totals["final_excess_ms_per_request_vs_hidden"] or 0.0
    output_post = totals["output_postprocess_ms_per_request"] or 0.0
    hidden_materialize = totals["hidden_materialize_ms_per_request"] or 0.0
    input_prepare = totals["input_prepare_ms_per_request"] or 0.0
    final_output_post = totals["final_output_postprocess_ms_per_request"] or 0.0
    decision = {
        "input_prepare_primary_bottleneck": input_prepare >= 0.5,
        "output_postprocess_primary_bottleneck": output_post >= final_excess,
        "hidden_materialize_buffer_reuse_has_measured_ceiling": hidden_materialize >= 0.5,
        "final_logits_compute_still_primary": final_excess > output_post
        and final_excess > hidden_materialize,
        "final_logits_output_postprocess_not_primary": final_output_post < 0.2,
        "post_instrumentation_measurement_complete": True,
        "next_local_runtime_code_target": (
            "seg27_28_last_token_logits_or_output_avoidance"
            if final_excess > hidden_materialize
            else "hidden_materialize_buffer_reuse"
        ),
        "secondary_local_runtime_code_target": (
            "hidden_materialize_buffer_reuse" if hidden_materialize >= 0.5 else None
        ),
        "do_not_run_more_standard_b4_sweeps_for_input_output_overhead": True,
    }
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_post_instrumentation_overhead_analysis",
        "source_paths": {"telemetry": str(args.telemetry)},
        "totals": totals,
        "rankings": {
            "top_output_postprocess_segments": ranked_segments(
                rows, "output_postprocess_ms", processed_request_count
            ),
            "top_hidden_materialize_segments": ranked_segments(
                rows, "hidden_materialize_ms", processed_request_count
            ),
            "top_input_prepare_segments": ranked_segments(
                rows, "input_prepare_ms", processed_request_count
            ),
        },
        "decision": decision,
        "audit": {
            "network_call_performed": False,
            "runtime_started": False,
            "compile_started": False,
            "source_telemetry_already_collected": True,
        },
    }


def render_md(path: Path, payload: dict[str, Any]) -> None:
    totals = payload["totals"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B=4 Post-Instrumentation Overhead Analysis",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- telemetry: `{payload['source_paths']['telemetry']}`",
        f"- ms_per_request: `{totals['ms_per_request']}`",
        f"- avg_bpu_loading: `{totals['avg_bpu_loading']}`",
        f"- input_prepare_ms_per_request: `{totals['input_prepare_ms_per_request']}`",
        f"- output_postprocess_ms_per_request: `{totals['output_postprocess_ms_per_request']}`",
        f"- hidden_materialize_ms_per_request: `{totals['hidden_materialize_ms_per_request']}`",
        f"- final_output_postprocess_ms_per_request: `{totals['final_output_postprocess_ms_per_request']}`",
        f"- final_excess_ms_per_request_vs_hidden: `{totals['final_excess_ms_per_request_vs_hidden']}`",
        f"- input_prepare_primary_bottleneck: `{decision['input_prepare_primary_bottleneck']}`",
        f"- output_postprocess_primary_bottleneck: `{decision['output_postprocess_primary_bottleneck']}`",
        f"- hidden_materialize_buffer_reuse_has_measured_ceiling: `{decision['hidden_materialize_buffer_reuse_has_measured_ceiling']}`",
        f"- final_logits_compute_still_primary: `{decision['final_logits_compute_still_primary']}`",
        f"- final_logits_output_postprocess_not_primary: `{decision['final_logits_output_postprocess_not_primary']}`",
        f"- next_local_runtime_code_target: `{decision['next_local_runtime_code_target']}`",
        f"- secondary_local_runtime_code_target: `{decision['secondary_local_runtime_code_target']}`",
        "",
        "## Top Output-Postprocess Segments",
        "",
        "| index | group | output_postprocess_ms_per_request | avg_run_ms |",
        "| ---: | --- | ---: | ---: |",
    ]
    for row in payload["rankings"]["top_output_postprocess_segments"][:5]:
        lines.append(
            f"| {row.get('index')} | {row.get('group')} | "
            f"{row.get('output_postprocess_ms_per_request')} | {row.get('avg_run_ms')} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--telemetry", type=Path, default=DEFAULT_TELEMETRY)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    write_json(args.out_json, payload)
    render_md(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
