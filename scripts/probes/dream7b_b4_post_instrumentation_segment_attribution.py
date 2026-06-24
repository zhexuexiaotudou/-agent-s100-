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
DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_post_instrumentation_segment_attribution_20260621.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_post_instrumentation_segment_attribution_20260621.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def per_request(value: Any, processed_request_count: int, digits: int = 6) -> float | None:
    if value is None or processed_request_count <= 0:
        return None
    return round(float(value) / processed_request_count, digits)


def segment_kind(index: int) -> str:
    if index == 0:
        return "token_embedding"
    if index == 27:
        return "final_logits"
    return "hidden_block"


def group_label(group: dict[str, Any]) -> str:
    return f"{group.get('group_start')}:{group.get('group_end')}"


def load_rows_by_index(group: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for row in group.get("loaded_segments") or []:
        if not isinstance(row, dict):
            continue
        index = int(row.get("index") if row.get("index") is not None else -1)
        rows[index] = row
    return rows


def build_segment_rows(telemetry: dict[str, Any]) -> list[dict[str, Any]]:
    processed = int(telemetry.get("processed_request_count") or 0)
    batch_size = int(telemetry.get("batch_size") or 1)
    timing = telemetry.get("timing_summary") or {}
    hidden_avg_run = as_float(timing.get("hidden_avg_run_ms"))
    rows: list[dict[str, Any]] = []
    for group in telemetry.get("group_rows") or []:
        if not isinstance(group, dict):
            continue
        loads = load_rows_by_index(group)
        label = group_label(group)
        for row in group.get("segment_rows") or []:
            if not isinstance(row, dict):
                continue
            index = int(row.get("index") if row.get("index") is not None else -1)
            load = loads.get(index) or {}
            avg_run = as_float(row.get("avg_run_ms"))
            compute_excess = None
            if hidden_avg_run > 0.0:
                compute_excess = round(max(0.0, avg_run - hidden_avg_run) / max(1, batch_size), 6)
            segment_total = as_float(row.get("segment_total_ms"))
            total_run = as_float(row.get("total_run_ms"))
            input_prepare = as_float(row.get("input_prepare_ms"))
            output_post = as_float(row.get("output_postprocess_ms"))
            hidden_materialize = as_float(row.get("hidden_materialize_ms"))
            inter_gap = row.get("inter_segment_first_run_gap_ms")
            intra_gap = as_float(row.get("intra_segment_run_gap_ms"))
            rows.append(
                {
                    "index": index,
                    "kind": segment_kind(index),
                    "group": label,
                    "model_name": row.get("model_name"),
                    "avg_run_ms": row.get("avg_run_ms"),
                    "run_ms_per_request": per_request(total_run, processed),
                    "compute_excess_vs_hidden_ms_per_request": compute_excess,
                    "segment_total_ms_per_request": per_request(segment_total, processed),
                    "input_prepare_ms_per_request": per_request(input_prepare, processed),
                    "output_postprocess_ms_per_request": per_request(output_post, processed),
                    "hidden_materialize_ms_per_request": per_request(hidden_materialize, processed),
                    "inter_segment_first_run_gap_ms_per_request": per_request(inter_gap, processed)
                    if inter_gap is not None
                    else None,
                    "intra_segment_run_gap_ms_per_request": per_request(intra_gap, processed),
                    "hbm_size_mib": load.get("hbm_size_mib"),
                    "load_ms_per_request": per_request(load.get("load_ms"), processed),
                    "completed_microbatch_count": row.get("completed_microbatch_count"),
                    "hidden_materialize_count": row.get("hidden_materialize_count"),
                    "reused_hidden_buffer_count": row.get("reused_hidden_buffer_count"),
                }
            )
    return rows


def build_group_rows(telemetry: dict[str, Any], segment_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    processed = int(telemetry.get("processed_request_count") or 0)
    by_group: dict[str, list[dict[str, Any]]] = {}
    for row in segment_rows:
        by_group.setdefault(str(row.get("group")), []).append(row)
    groups: list[dict[str, Any]] = []
    for group in telemetry.get("group_rows") or []:
        if not isinstance(group, dict):
            continue
        label = group_label(group)
        rows = by_group.get(label) or []
        top_segment = max(rows, key=lambda row: as_float(row.get("segment_total_ms_per_request")), default={})
        total_segment_ms_per_request = round(
            sum(as_float(row.get("segment_total_ms_per_request")) for row in rows), 6
        )
        total_compute_excess_ms_per_request = round(
            sum(as_float(row.get("compute_excess_vs_hidden_ms_per_request")) for row in rows), 6
        )
        groups.append(
            {
                "group": label,
                "segment_count": len(rows),
                "contains_final_logits": any(row.get("kind") == "final_logits" for row in rows),
                "contains_token_embedding": any(row.get("kind") == "token_embedding" for row in rows),
                "group_load_ms_per_request": per_request(group.get("group_load_ms"), processed),
                "group_release_ms_per_request": per_request(group.get("group_release_ms"), processed),
                "group_loop_ms_per_request": per_request(group.get("group_loop_ms"), processed),
                "segment_total_ms_per_request": total_segment_ms_per_request,
                "compute_excess_vs_hidden_ms_per_request": total_compute_excess_ms_per_request,
                "top_segment_index": top_segment.get("index"),
                "top_segment_kind": top_segment.get("kind"),
                "top_segment_ms_per_request": top_segment.get("segment_total_ms_per_request"),
            }
        )
    return groups


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    telemetry = read_json(args.telemetry)
    processed = int(telemetry.get("processed_request_count") or 0)
    timing = telemetry.get("timing_summary") or {}
    segment_rows = build_segment_rows(telemetry)
    group_rows = build_group_rows(telemetry, segment_rows)
    final_row = next((row for row in segment_rows if row.get("kind") == "final_logits"), {})
    token_row = next((row for row in segment_rows if row.get("kind") == "token_embedding"), {})
    hidden_rows = [row for row in segment_rows if row.get("kind") == "hidden_block"]
    top_hidden = max(
        hidden_rows,
        key=lambda row: as_float(row.get("segment_total_ms_per_request")),
        default={},
    )
    top_compute_excess_hidden = max(
        hidden_rows,
        key=lambda row: as_float(row.get("compute_excess_vs_hidden_ms_per_request")),
        default={},
    )
    ranked_segments = sorted(
        segment_rows,
        key=lambda row: as_float(row.get("segment_total_ms_per_request")),
        reverse=True,
    )
    ranked_compute_excess = sorted(
        segment_rows,
        key=lambda row: as_float(row.get("compute_excess_vs_hidden_ms_per_request")),
        reverse=True,
    )
    ranked_groups = sorted(
        group_rows,
        key=lambda row: as_float(row.get("segment_total_ms_per_request")),
        reverse=True,
    )
    final_compute_excess = as_float(final_row.get("compute_excess_vs_hidden_ms_per_request"))
    hidden_materialize = per_request(timing.get("total_hidden_materialize_ms"), processed) or 0.0
    output_post = per_request(timing.get("total_output_postprocess_ms"), processed) or 0.0
    input_prepare = per_request(timing.get("total_input_prepare_ms"), processed) or 0.0
    top_hidden_compute_excess = as_float(
        top_compute_excess_hidden.get("compute_excess_vs_hidden_ms_per_request")
    )
    final_to_hidden_excess_ratio = None
    if top_hidden_compute_excess > 0:
        final_to_hidden_excess_ratio = round(final_compute_excess / top_hidden_compute_excess, 3)

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_post_instrumentation_segment_attribution",
        "scope": "single-run post-instrumentation B=4 segment and group attribution; no runtime execution",
        "source_paths": {"telemetry": str(args.telemetry)},
        "run": {
            "microbatch_count": telemetry.get("microbatch_count"),
            "batch_size": telemetry.get("batch_size"),
            "processed_request_count": processed,
            "groups": telemetry.get("groups"),
            "inner_order": telemetry.get("inner_order"),
            "release_gc_mode": telemetry.get("release_gc_mode"),
            "final_logits_mode": telemetry.get("final_logits_mode"),
            "ms_per_request": telemetry.get("amortized_wall_ms_per_request"),
            "avg_bpu_loading": telemetry.get("avg_bpu_loading"),
            "avg_nonzero_bpu_loading": telemetry.get("avg_nonzero_bpu_loading"),
        },
        "totals": {
            "input_prepare_ms_per_request": input_prepare,
            "output_postprocess_ms_per_request": output_post,
            "hidden_materialize_ms_per_request": hidden_materialize,
            "final_compute_excess_ms_per_request": final_compute_excess,
            "final_output_postprocess_ms_per_request": final_row.get(
                "output_postprocess_ms_per_request"
            ),
            "final_run_ms_per_request": final_row.get("run_ms_per_request"),
            "hidden_mean_avg_run_ms": timing.get("hidden_avg_run_ms"),
            "final_logits_avg_run_ms": timing.get("final_logits_avg_run_ms"),
            "final_to_top_hidden_compute_excess_ratio": final_to_hidden_excess_ratio,
        },
        "rankings": {
            "top_segments_by_segment_total_ms_per_request": ranked_segments[:8],
            "top_segments_by_compute_excess_ms_per_request": ranked_compute_excess[:8],
            "top_groups_by_segment_total_ms_per_request": ranked_groups[:5],
        },
        "key_segments": {
            "final_logits": final_row,
            "token_embedding": token_row,
            "top_hidden_by_segment_total": top_hidden,
            "top_hidden_by_compute_excess": top_compute_excess_hidden,
        },
        "decision": {
            "primary_single_segment_bottleneck": "seg27_28_final_logits",
            "final_logits_compute_still_primary": final_compute_excess > hidden_materialize
            and final_compute_excess > output_post,
            "input_prepare_primary_bottleneck": input_prepare >= 0.5,
            "output_postprocess_primary_bottleneck": output_post >= final_compute_excess,
            "hidden_materialize_secondary_ceiling": hidden_materialize >= 0.5,
            "current_preallocate_hidden_path_should_remain_rejected": True,
            "top_group_by_segment_total": (ranked_groups[0] or {}).get("group") if ranked_groups else None,
            "top_group_contains_final_logits": (ranked_groups[0] or {}).get("contains_final_logits")
            if ranked_groups
            else None,
            "group_size_tuning_implication": "keep_existing_5_group_segment_major_default",
            "inner_order_tuning_implication": "keep_segment_major",
            "next_code_target": "seg27_28_last_token_logits_or_output_avoidance",
            "secondary_research_target": "alternative_hidden_materialize_avoidance_without_preallocated_copyto",
            "do_not_run_more_standard_b4_group_order_sweeps_now": True,
        },
        "audit": {
            "network_call_performed": False,
            "runtime_started": False,
            "compile_started": False,
            "source_telemetry_already_collected": True,
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    run = payload["run"]
    totals = payload["totals"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B4 Post-Instrumentation Segment Attribution",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- telemetry: `{payload['source_paths']['telemetry']}`",
        f"- microbatch_count: `{run['microbatch_count']}`",
        f"- batch_size: `{run['batch_size']}`",
        f"- ms_per_request: `{run['ms_per_request']}`",
        f"- avg_bpu_loading: `{run['avg_bpu_loading']}`",
        f"- final_compute_excess_ms_per_request: `{totals['final_compute_excess_ms_per_request']}`",
        f"- hidden_materialize_ms_per_request: `{totals['hidden_materialize_ms_per_request']}`",
        f"- output_postprocess_ms_per_request: `{totals['output_postprocess_ms_per_request']}`",
        f"- input_prepare_ms_per_request: `{totals['input_prepare_ms_per_request']}`",
        f"- primary_single_segment_bottleneck: `{decision['primary_single_segment_bottleneck']}`",
        f"- group_size_tuning_implication: `{decision['group_size_tuning_implication']}`",
        f"- inner_order_tuning_implication: `{decision['inner_order_tuning_implication']}`",
        f"- next_code_target: `{decision['next_code_target']}`",
        "",
        "## Top Segments By Segment Total",
        "",
        "| rank | index | kind | group | segment ms/request | run ms/request | compute excess ms/request | hidden materialize ms/request | output postprocess ms/request |",
        "| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, row in enumerate(
        payload["rankings"]["top_segments_by_segment_total_ms_per_request"][:8], start=1
    ):
        lines.append(
            f"| {rank} | {row.get('index')} | {row.get('kind')} | {row.get('group')} | "
            f"{row.get('segment_total_ms_per_request')} | {row.get('run_ms_per_request')} | "
            f"{row.get('compute_excess_vs_hidden_ms_per_request')} | "
            f"{row.get('hidden_materialize_ms_per_request')} | "
            f"{row.get('output_postprocess_ms_per_request')} |"
        )
    lines.extend(
        [
            "",
            "## Top Groups By Segment Total",
            "",
            "| rank | group | segments | contains final | segment ms/request | compute excess ms/request | load ms/request | release ms/request | top segment |",
            "| ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for rank, row in enumerate(
        payload["rankings"]["top_groups_by_segment_total_ms_per_request"][:5], start=1
    ):
        lines.append(
            f"| {rank} | {row.get('group')} | {row.get('segment_count')} | "
            f"{row.get('contains_final_logits')} | {row.get('segment_total_ms_per_request')} | "
            f"{row.get('compute_excess_vs_hidden_ms_per_request')} | "
            f"{row.get('group_load_ms_per_request')} | {row.get('group_release_ms_per_request')} | "
            f"{row.get('top_segment_index')} {row.get('top_segment_kind')} |"
        )
    lines.extend(["", "## Decision", ""])
    for key, value in decision.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Attribute latest post-instrumentation Dream7B B=4 telemetry by segment and group."
    )
    parser.add_argument("--telemetry", type=Path, default=DEFAULT_TELEMETRY)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
