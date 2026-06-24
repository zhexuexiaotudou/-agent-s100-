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


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    attribution = load_json(args.final_output_attribution_json)
    latest = attribution["latest_default_b4"]
    batch_size = as_int(latest.get("batch_size"))
    final_shape = latest.get("final_shape") or [batch_size, args.seq_len, args.vocab_size]
    if len(final_shape) != 3:
        raise SystemExit(f"unexpected final_shape: {final_shape}")
    _batch, seq_len, vocab_size = (as_int(item) for item in final_shape)
    if batch_size <= 0:
        batch_size = _batch

    processed = as_int(latest.get("processed_request_count"))
    microbatches = as_int(latest.get("microbatch_count"))
    final_avg_run_ms = as_float(latest.get("final_avg_run_ms"))
    hidden_avg_run_ms = as_float(latest.get("hidden_mean_avg_run_ms"))
    final_run_ms_per_request = as_float(latest.get("final_run_ms_per_request"))
    final_excess_ms_per_request = as_float(latest.get("final_excess_ms_per_request_if_hidden_speed"))
    final_overhead_ms_per_request = as_float(latest.get("final_segment_overhead_ms_per_request"))

    bytes_per_f32 = 4
    current_elements_per_microbatch = batch_size * seq_len * vocab_size
    last_token_elements_per_microbatch = batch_size * vocab_size
    current_f32_bytes_per_microbatch = current_elements_per_microbatch * bytes_per_f32
    last_token_f32_bytes_per_microbatch = last_token_elements_per_microbatch * bytes_per_f32
    current_f32_bytes_per_request = current_f32_bytes_per_microbatch / batch_size
    last_token_f32_bytes_per_request = last_token_f32_bytes_per_microbatch / batch_size
    output_element_reduction = (
        current_elements_per_microbatch / last_token_elements_per_microbatch
        if last_token_elements_per_microbatch
        else None
    )

    final_excess_ms_per_microbatch = max(0.0, final_avg_run_ms - hidden_avg_run_ms)
    projected_saved_ms_per_microbatch = final_excess_ms_per_microbatch * max(0, seq_len - 1) / max(1, seq_len)
    projected_final_avg_run_ms = final_avg_run_ms - projected_saved_ms_per_microbatch
    projected_final_run_ms_per_request = projected_final_avg_run_ms / batch_size if batch_size else None
    projected_saved_ms_per_request = projected_saved_ms_per_microbatch / batch_size if batch_size else None

    topk_rows: list[dict[str, Any]] = []
    for top_k in args.top_k:
        topk_bytes_per_request = top_k * (args.token_id_bytes + args.score_bytes)
        topk_bytes_per_microbatch = batch_size * topk_bytes_per_request
        topk_rows.append(
            {
                "top_k": top_k,
                "bytes_per_request": topk_bytes_per_request,
                "bytes_per_microbatch": topk_bytes_per_microbatch,
                "reduction_vs_current_f32_per_request": round_or_none(
                    current_f32_bytes_per_request / topk_bytes_per_request
                    if topk_bytes_per_request
                    else None,
                    3,
                ),
            }
        )

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_b4_final_logits_candidate_sizing",
        "source_paths": {
            "final_output_attribution": str(args.final_output_attribution_json),
        },
        "current": {
            "latest_default_file": latest.get("name"),
            "batch_size": batch_size,
            "seq_len": seq_len,
            "vocab_size": vocab_size,
            "microbatch_count": microbatches,
            "processed_request_count": processed,
            "final_shape": final_shape,
            "final_avg_run_ms_per_microbatch": final_avg_run_ms,
            "hidden_mean_avg_run_ms_per_microbatch": hidden_avg_run_ms,
            "final_run_ms_per_request": final_run_ms_per_request,
            "final_excess_ms_per_request_if_hidden_speed": final_excess_ms_per_request,
            "final_segment_overhead_ms_per_request": final_overhead_ms_per_request,
            "current_f32_output_bytes_per_microbatch": current_f32_bytes_per_microbatch,
            "current_f32_output_mib_per_microbatch": round_or_none(current_f32_bytes_per_microbatch / (1024 * 1024)),
            "current_f32_output_bytes_per_request": round_or_none(current_f32_bytes_per_request, 3),
            "current_f32_output_mib_per_request": round_or_none(current_f32_bytes_per_request / (1024 * 1024)),
        },
        "last_token_logits_candidate": {
            "target_shape": [batch_size, 1, vocab_size],
            "f32_output_bytes_per_microbatch": last_token_f32_bytes_per_microbatch,
            "f32_output_mib_per_microbatch": round_or_none(last_token_f32_bytes_per_microbatch / (1024 * 1024)),
            "f32_output_bytes_per_request": round_or_none(last_token_f32_bytes_per_request, 3),
            "f32_output_mib_per_request": round_or_none(last_token_f32_bytes_per_request / (1024 * 1024)),
            "output_element_reduction_vs_current": round_or_none(output_element_reduction, 3),
            "projection_only_hypothesis_saved_ms_per_request": round_or_none(projected_saved_ms_per_request),
            "projection_only_hypothesis_final_run_ms_per_request": round_or_none(projected_final_run_ms_per_request),
            "projection_only_hypothesis_final_avg_run_ms_per_microbatch": round_or_none(projected_final_avg_run_ms),
        },
        "topk_payload_candidates": topk_rows,
        "decision": {
            "group_boundary_sweeps_deprioritized": True,
            "compile_candidate": "seg27_28_last_token_logits",
            "runtime_probe_change": "accept_final_shape_batch_1_vocab_for_final_segment_and_load_seg27_from_final_hbm_root",
            "promotion_gate": "only_compare_after_single_segment_compile_and_mb512_runtime_validation",
        },
        "interpretation": [
            "The current B4 final output is [B,16,V], but decoding only needs last-token logits for next-token selection.",
            "A last-token-only logits segment would reduce the final logits output element count by 16x for seq16.",
            "Because measured Python/output overhead is only about 0.094 ms/request, the useful win must come from reducing the compiled lm_head work, not from moving fewer bytes in Python.",
            "Under a projection-only scaling hypothesis, removing 15/16 of the final vocab projection would recover about the same 3 ms/request excess identified by segment drag analysis.",
            "The next low-risk experiment is a single seg27_28_last_token_logits compile plus a runtime probe variant that accepts [B,1,V] only for the final segment.",
        ],
    }


def render_md(payload: dict[str, Any], out_md: Path) -> None:
    current = payload["current"]
    candidate = payload["last_token_logits_candidate"]
    lines = [
        "# Dream7B B4 Final Logits Candidate Sizing",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- current_final_shape: {current['final_shape']}",
        f"- candidate_target_shape: {candidate['target_shape']}",
        f"- output_element_reduction_vs_current: {candidate['output_element_reduction_vs_current']}x",
        f"- current_f32_output_mib_per_request: {current['current_f32_output_mib_per_request']}",
        f"- last_token_f32_output_mib_per_request: {candidate['f32_output_mib_per_request']}",
        f"- measured_final_segment_overhead_ms_per_request: {current['final_segment_overhead_ms_per_request']}",
        f"- measured_final_excess_ms_per_request_if_hidden_speed: {current['final_excess_ms_per_request_if_hidden_speed']}",
        f"- projection_only_saved_ms_per_request: {candidate['projection_only_hypothesis_saved_ms_per_request']}",
        f"- projection_only_final_run_ms_per_request: {candidate['projection_only_hypothesis_final_run_ms_per_request']}",
        "",
        "## Current Final Segment",
        "",
    ]
    for key, value in current.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Last-Token Logits Candidate", ""])
    for key, value in candidate.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Top-K Payload Candidates",
            "",
            "| top_k | bytes/request | bytes/microbatch | reduction_vs_current_f32/request |",
            "| ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["topk_payload_candidates"]:
        lines.append(
            f"| {row['top_k']} | {row['bytes_per_request']} | {row['bytes_per_microbatch']} | "
            f"{row['reduction_vs_current_f32_per_request']}x |"
        )
    lines.extend(["", "## Decision", ""])
    lines.extend(f"- {key}: {value}" for key, value in payload["decision"].items())
    lines.extend(["", "## Interpretation", ""])
    lines.extend(f"- {item}" for item in payload["interpretation"])
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Size the B4 last-token final logits candidate from telemetry.")
    parser.add_argument(
        "--final-output-attribution-json",
        type=Path,
        default=Path("tmp/b4_runtime_schedule_analysis_20260619/dream7b_b4_final_output_attribution_20260619.json"),
    )
    parser.add_argument("--seq-len", type=int, default=16)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--token-id-bytes", type=int, default=4)
    parser.add_argument("--score-bytes", type=int, default=4)
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/b4_runtime_schedule_analysis_20260619"))
    parser.add_argument("--out-stem", default="dream7b_b4_final_logits_candidate_sizing_20260619")
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
