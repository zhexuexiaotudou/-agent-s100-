#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_true_batch_runtime_instrumentation_contract"
DEFAULT_SOURCE = Path("scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py")
DEFAULT_OUT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")


def line_number(text: str, token: str) -> int | None:
    for lineno, line in enumerate(text.splitlines(), start=1):
        if token in line:
            return lineno
    return None


def build_contract(source_path: Path) -> dict[str, Any]:
    text = source_path.read_text(encoding="utf-8")
    required_tokens = {
        "input_prepare_summary": '"total_input_prepare_ms"',
        "input_prepare_fraction": '"input_prepare_fraction_of_wall"',
        "output_postprocess_summary": '"total_output_postprocess_ms"',
        "output_postprocess_fraction": '"output_postprocess_fraction_of_wall"',
        "segment_input_prepare": '"input_prepare_ms"',
        "segment_avg_input_prepare": '"avg_input_prepare_ms"',
        "segment_output_postprocess": '"output_postprocess_ms"',
        "segment_avg_output_postprocess": '"avg_output_postprocess_ms"',
        "microbatch_input_prepare_accumulator": "input_prepare_ms += float(item_row.get",
        "microbatch_output_postprocess_accumulator": "output_postprocess_ms += float(item_row.get",
        "group_loop_ms": '"group_loop_ms"',
        "group_load_ms": '"group_load_ms"',
        "group_release_ms": '"group_release_ms"',
        "loaded_segments": '"loaded_segments"',
        "total_group_load_ms": '"total_group_load_ms"',
        "total_group_release_ms": '"total_group_release_ms"',
        "total_inter_segment_first_run_gap_ms": '"total_inter_segment_first_run_gap_ms"',
        "total_intra_segment_run_gap_ms": '"total_intra_segment_run_gap_ms"',
        "segment_inter_segment_first_run_gap": '"inter_segment_first_run_gap_ms"',
        "segment_intra_segment_run_gap": '"intra_segment_run_gap_ms"',
        "final_logits_mode": '"final_logits_mode"',
        "final_hbm_root": '"final_hbm_root"',
        "expected_final_shape": '"expected_final_shape"',
        "final_shape": '"final_shape"',
    }
    token_checks = {
        name: {
            "token": token,
            "present": token in text,
            "line": line_number(text, token),
        }
        for name, token in required_tokens.items()
    }
    missing = [name for name, row in token_checks.items() if not row["present"]]
    new_fields = [
        "total_input_prepare_ms",
        "input_prepare_fraction_of_wall",
        "total_output_postprocess_ms",
        "output_postprocess_fraction_of_wall",
        "input_prepare_ms",
        "avg_input_prepare_ms",
        "output_postprocess_ms",
        "avg_output_postprocess_ms",
        "group_loop_ms",
        "group_load_ms",
        "group_release_ms",
        "loaded_segments",
        "total_group_load_ms",
        "total_group_release_ms",
        "total_inter_segment_first_run_gap_ms",
        "total_intra_segment_run_gap_ms",
        "inter_segment_first_run_gap_ms",
        "intra_segment_run_gap_ms",
        "final_logits_mode",
        "final_hbm_root",
        "expected_final_shape",
        "final_shape",
    ]
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": (
            "ok_dream7b_true_batch_runtime_instrumentation_contract"
            if not missing
            else "failed_dream7b_true_batch_runtime_instrumentation_contract"
        ),
        "source_path": str(source_path),
        "new_telemetry_fields": new_fields,
        "checks": token_checks,
        "missing_checks": missing,
        "behavior": {
            "default_cli_changed": False,
            "runtime_order_changed": False,
            "requires_s100p_runtime": False,
            "writes_runtime_reports_only_when_probe_runs": True,
        },
        "purpose": (
            "Expose input preparation and output postprocess timing in the existing true-batch "
            "group-major telemetry report and verify the existing group-loop/load/release, "
            "loaded-segment, inter/intra-segment gap, and final-logits shape fields so future "
            "S100P runs can separate Python preparation overhead from runtime.run, hidden "
            "materialization, group-switch gaps, and final-logits output mode changes."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Dream7B true-batch runtime instrumentation fields.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    args = parser.parse_args()

    payload = build_contract(args.source)
    args.out_root.mkdir(parents=True, exist_ok=True)
    json_path = args.out_root / "dream7b_true_batch_runtime_instrumentation_contract_20260621.json"
    md_path = args.out_root / "dream7b_true_batch_runtime_instrumentation_contract_20260621.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream7B True-Batch Runtime Instrumentation Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- source_path: `{payload['source_path']}`",
        f"- default_cli_changed: `{payload['behavior']['default_cli_changed']}`",
        f"- runtime_order_changed: `{payload['behavior']['runtime_order_changed']}`",
        f"- requires_s100p_runtime: `{payload['behavior']['requires_s100p_runtime']}`",
        f"- new_telemetry_fields: `{payload['new_telemetry_fields']}`",
        "",
        "## Checks",
        "",
    ]
    for name, row in payload["checks"].items():
        lines.append(f"- {name}: present `{row['present']}` line `{row['line']}`")
    if payload["missing_checks"]:
        lines.extend(["", "## Missing", ""])
        lines.extend(f"- {item}" for item in payload["missing_checks"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json_path, flush=True)
    print(md_path, flush=True)
    return 0 if not payload["missing_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
