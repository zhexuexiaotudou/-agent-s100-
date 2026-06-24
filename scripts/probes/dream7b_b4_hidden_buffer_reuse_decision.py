#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ANALYSIS_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_PREALLOC_AB = DEFAULT_ANALYSIS_ROOT / "dream7b_b4_prealloc_hidden_ab_20260619.json"
DEFAULT_POST_OVERHEAD = (
    DEFAULT_ANALYSIS_ROOT / "dream7b_b4_post_instrumentation_overhead_analysis_20260621.json"
)
DEFAULT_OUT_JSON = DEFAULT_ANALYSIS_ROOT / "dream7b_b4_hidden_buffer_reuse_decision_20260621.json"
DEFAULT_OUT_MD = DEFAULT_ANALYSIS_ROOT / "dream7b_b4_hidden_buffer_reuse_decision_20260621.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def metric_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("metric")): row for row in rows}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    prealloc = read_json(args.prealloc_ab)
    post_overhead = read_json(args.post_overhead)
    rows = metric_rows(prealloc.get("rows") or [])
    post_totals = post_overhead.get("totals") or {}
    post_decision = post_overhead.get("decision") or {}
    latest_delta = {
        "ms_per_request_delta": (rows.get("ms_per_request") or {}).get(
            "delta_prealloc_minus_no_prealloc"
        ),
        "hidden_materialize_ms_per_request_delta": (
            rows.get("hidden_materialize_ms_per_request") or {}
        ).get("delta_prealloc_minus_no_prealloc"),
        "avg_bpu_delta": (rows.get("avg_bpu") or {}).get("delta_prealloc_minus_no_prealloc"),
        "nonzero_bpu_delta": (rows.get("nonzero_bpu") or {}).get(
            "delta_prealloc_minus_no_prealloc"
        ),
        "reused_hidden_buffer_count": (rows.get("reused_hidden_buffer_count") or {}).get(
            "prealloc"
        ),
        "reused_hidden_buffer_count_delta": (
            rows.get("reused_hidden_buffer_count") or {}
        ).get("delta_prealloc_minus_no_prealloc"),
    }
    decision = {
        "hidden_buffer_reuse_default": False,
        "preallocate_hidden_experimental_flag_only": True,
        "do_not_start_new_preallocate_hidden_runtime_now": True,
        "do_not_change_runtime_defaults_now": True,
        "reuse_buffer_implementation_measured_slower": (
            (latest_delta["ms_per_request_delta"] or 0) > 0
            and (latest_delta["hidden_materialize_ms_per_request_delta"] or 0) > 0
        ),
        "hidden_materialize_has_measured_ceiling": post_decision.get(
            "hidden_materialize_buffer_reuse_has_measured_ceiling"
        )
        is True,
        "primary_target_remains_final_logits": post_decision.get(
            "final_logits_compute_still_primary"
        )
        is True,
        "next_code_target": post_decision.get("next_local_runtime_code_target"),
        "secondary_research_target": "alternative_hidden_materialize_avoidance_without_preallocated_copyto",
    }
    verdict = "ok_dream7b_b4_hidden_buffer_reuse_decision"
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "source_paths": {
            "prealloc_ab": str(args.prealloc_ab),
            "post_instrumentation_overhead": str(args.post_overhead),
        },
        "post_instrumentation_reference": {
            "hidden_materialize_ms_per_request": post_totals.get(
                "hidden_materialize_ms_per_request"
            ),
            "final_excess_ms_per_request_vs_hidden": post_totals.get(
                "final_excess_ms_per_request_vs_hidden"
            ),
            "input_prepare_ms_per_request": post_totals.get("input_prepare_ms_per_request"),
            "output_postprocess_ms_per_request": post_totals.get(
                "output_postprocess_ms_per_request"
            ),
        },
        "latest_prealloc_ab_delta": latest_delta,
        "decision": decision,
        "audit": {
            "network_call_performed": False,
            "runtime_started": False,
            "compile_started": False,
            "local_json_md_only": True,
        },
    }


def render_md(path: Path, payload: dict[str, Any]) -> None:
    ref = payload["post_instrumentation_reference"]
    delta = payload["latest_prealloc_ab_delta"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B=4 Hidden Buffer Reuse Decision",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- hidden_materialize_ms_per_request: `{ref['hidden_materialize_ms_per_request']}`",
        f"- final_excess_ms_per_request_vs_hidden: `{ref['final_excess_ms_per_request_vs_hidden']}`",
        f"- prealloc_ms_per_request_delta: `{delta['ms_per_request_delta']}`",
        f"- prealloc_hidden_materialize_ms_per_request_delta: `{delta['hidden_materialize_ms_per_request_delta']}`",
        f"- prealloc_reused_hidden_buffer_count: `{delta['reused_hidden_buffer_count']}`",
        f"- hidden_buffer_reuse_default: `{decision['hidden_buffer_reuse_default']}`",
        f"- preallocate_hidden_experimental_flag_only: `{decision['preallocate_hidden_experimental_flag_only']}`",
        f"- do_not_start_new_preallocate_hidden_runtime_now: `{decision['do_not_start_new_preallocate_hidden_runtime_now']}`",
        f"- reuse_buffer_implementation_measured_slower: `{decision['reuse_buffer_implementation_measured_slower']}`",
        f"- primary_target_remains_final_logits: `{decision['primary_target_remains_final_logits']}`",
        f"- secondary_research_target: `{decision['secondary_research_target']}`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prealloc-ab", type=Path, default=DEFAULT_PREALLOC_AB)
    parser.add_argument("--post-overhead", type=Path, default=DEFAULT_POST_OVERHEAD)
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
