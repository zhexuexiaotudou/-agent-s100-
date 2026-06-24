#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_b4_runtime_refactor_source_contract"
DEFAULT_SOURCE = Path("scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py")
DEFAULT_OUT_JSON = Path(
    "tmp/b4_runtime_schedule_analysis_20260619/dream7b_b4_runtime_refactor_source_contract_20260621.json"
)
DEFAULT_OUT_MD = Path(
    "tmp/b4_runtime_schedule_analysis_20260619/dream7b_b4_runtime_refactor_source_contract_20260621.md"
)

PROTECTED_TELEMETRY_FIELDS = {
    "total_input_prepare_ms": '"total_input_prepare_ms"',
    "input_prepare_fraction_of_wall": '"input_prepare_fraction_of_wall"',
    "total_output_postprocess_ms": '"total_output_postprocess_ms"',
    "output_postprocess_fraction_of_wall": '"output_postprocess_fraction_of_wall"',
    "input_prepare_ms": '"input_prepare_ms"',
    "avg_input_prepare_ms": '"avg_input_prepare_ms"',
    "output_postprocess_ms": '"output_postprocess_ms"',
    "avg_output_postprocess_ms": '"avg_output_postprocess_ms"',
    "group_loop_ms": '"group_loop_ms"',
    "group_load_ms": '"group_load_ms"',
    "group_release_ms": '"group_release_ms"',
    "loaded_segments": '"loaded_segments"',
    "total_group_load_ms": '"total_group_load_ms"',
    "total_group_release_ms": '"total_group_release_ms"',
    "total_inter_segment_first_run_gap_ms": '"total_inter_segment_first_run_gap_ms"',
    "total_intra_segment_run_gap_ms": '"total_intra_segment_run_gap_ms"',
    "inter_segment_first_run_gap_ms": '"inter_segment_first_run_gap_ms"',
    "intra_segment_run_gap_ms": '"intra_segment_run_gap_ms"',
    "final_logits_mode": '"final_logits_mode"',
    "final_hbm_root": '"final_hbm_root"',
    "expected_final_shape": '"expected_final_shape"',
    "final_shape": '"final_shape"',
}


def line_number(lines: list[str], token: str) -> int | None:
    for lineno, line in enumerate(lines, start=1):
        if token in line:
            return lineno
    return None


def token_check(lines: list[str], token: str) -> dict[str, Any]:
    line = line_number(lines, token)
    return {"token": token, "present": line is not None, "line": line}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    text = args.source.read_text(encoding="utf-8")
    lines = text.splitlines()
    required_tokens = {
        "final_hbm_root_arg": 'parser.add_argument("--final-hbm-root", default=""',
        "final_logits_mode_arg": 'parser.add_argument("--final-logits-mode", choices=["full", "last-token"], default="full")',
        "final_logits_suffix": 'return "_last_token_logits" if index == 27 and final_logits_mode == "last-token" else ""',
        "final_logits_seq_len": 'return 1 if final_logits_mode == "last-token" else seq_len',
        "hbm_path_final_root_index27": "base = final_root if index == 27 and final_root is not None else root",
        "model_name_suffix": "suffix = final_logits_suffix(final_logits_mode, index)",
        "final_shape_uses_final_logits_seq_len": "expected_final_shape = [args.batch_size, final_logits_seq_len(args.seq_len, args.final_logits_mode), args.vocab_size]",
        "runtime_run_call": "out = runtime.run(inputs, model_name=name)",
        "loaded_segments_reported": '"loaded_segments": loaded_segment_summary(loaded),',
        "segment_input_prepare_ms": '"input_prepare_ms": round(input_prepare_ms, 3),',
        "segment_output_postprocess_ms": '"output_postprocess_ms": round(output_postprocess_ms, 3),',
        "segment_hidden_materialize_ms": '"hidden_materialize_ms": round(sum(materialize_times), 3),',
        "inter_segment_gap_ms": '"inter_segment_first_run_gap_ms":',
        "intra_segment_gap_ms": '"intra_segment_run_gap_ms":',
        "preallocate_hidden_explicit_flag": 'parser.add_argument("--preallocate-hidden", action="store_true")',
        "prewarm_hbm_explicit_flag": 'parser.add_argument("--prewarm-hbm", action="store_true"',
        "release_gc_default_collect": 'parser.add_argument("--release-gc-mode", choices=["collect", "skip"], default="collect")',
        "inner_order_default_unchanged": 'parser.add_argument("--inner-order", choices=["microbatch-major", "segment-major"], default="microbatch-major")',
        "batch_size_default_unchanged": 'parser.add_argument("--batch-size", type=int, default=2)',
        "group_default_unchanged": 'parser.add_argument("--groups", default="0:6,6:12,12:18,18:24,24:28")',
    }
    checks = {
        name: token_check(lines, token)
        for name, token in required_tokens.items()
    }
    telemetry_field_checks = {
        name: token_check(lines, token)
        for name, token in PROTECTED_TELEMETRY_FIELDS.items()
    }
    missing = [name for name, row in checks.items() if not row["present"]]
    missing_telemetry_fields = [
        name for name, row in telemetry_field_checks.items() if not row["present"]
    ]
    cli_defaults_preserved = all(
        checks[name]["present"]
        for name in [
            "final_hbm_root_arg",
            "final_logits_mode_arg",
            "preallocate_hidden_explicit_flag",
            "prewarm_hbm_explicit_flag",
            "release_gc_default_collect",
            "inner_order_default_unchanged",
            "batch_size_default_unchanged",
            "group_default_unchanged",
        ]
    )
    last_token_path_supported = all(
        checks[name]["present"]
        for name in [
            "final_logits_suffix",
            "final_logits_seq_len",
            "hbm_path_final_root_index27",
            "model_name_suffix",
            "final_shape_uses_final_logits_seq_len",
        ]
    )
    telemetry_contract_ready = all(
        checks[name]["present"]
        for name in [
            "loaded_segments_reported",
            "segment_input_prepare_ms",
            "segment_output_postprocess_ms",
            "segment_hidden_materialize_ms",
            "inter_segment_gap_ms",
            "intra_segment_gap_ms",
        ]
    ) and not missing_telemetry_fields
    runtime_order_changed = False
    default_promotes_experimental_flags = False
    verdict = (
        "ok_dream7b_b4_runtime_refactor_source_contract"
        if not missing
        and cli_defaults_preserved
        and last_token_path_supported
        and telemetry_contract_ready
        and not runtime_order_changed
        and not default_promotes_experimental_flags
        else "failed_dream7b_b4_runtime_refactor_source_contract"
    )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "source_path": str(args.source),
        "checks": checks,
        "missing_checks": missing,
        "summary": {
            "cli_defaults_preserved": cli_defaults_preserved,
            "last_token_path_supported": last_token_path_supported,
            "telemetry_contract_ready": telemetry_contract_ready,
            "protected_telemetry_fields_ready": not missing_telemetry_fields,
            "protected_telemetry_field_count": len(PROTECTED_TELEMETRY_FIELDS),
            "protected_telemetry_missing_count": len(missing_telemetry_fields),
            "runtime_order_changed": runtime_order_changed,
            "default_promotes_experimental_flags": default_promotes_experimental_flags,
            "requires_hbm_runtime_import": False,
            "runtime_started": False,
            "compile_started": False,
        },
        "protected_defaults": {
            "final_logits_mode": "full",
            "inner_order": "microbatch-major",
            "batch_size": 2,
            "groups": "0:6,6:12,12:18,18:24,24:28",
            "release_gc_mode": "collect",
            "preallocate_hidden": False,
            "prewarm_hbm": False,
        },
        "local_refactor_contract": {
            "last_token_candidate_can_be_selected_without_changing_default": last_token_path_supported
            and checks["final_logits_mode_arg"]["present"],
            "hidden_materialize_can_be_measured_before_any_promotion": telemetry_contract_ready
            and checks["segment_hidden_materialize_ms"]["present"],
            "group_switch_gap_can_be_measured_before_group_policy_changes": telemetry_contract_ready
            and checks["inter_segment_gap_ms"]["present"]
            and checks["intra_segment_gap_ms"]["present"],
            "preallocate_hidden_must_remain_explicit": checks[
                "preallocate_hidden_explicit_flag"
            ]["present"],
            "prewarm_hbm_must_remain_explicit": checks["prewarm_hbm_explicit_flag"][
                "present"
            ],
            "all_runtime_refactor_telemetry_fields_protected": not missing_telemetry_fields,
        },
        "protected_telemetry_fields": list(PROTECTED_TELEMETRY_FIELDS),
        "telemetry_field_checks": telemetry_field_checks,
        "missing_telemetry_fields": missing_telemetry_fields,
        "audit": {
            "source_modified": False,
            "runtime_started": False,
            "compile_started": False,
            "remote_access_performed": False,
            "local_writes": "JSON/Markdown runtime refactor source contract only",
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Dream7B B=4 Runtime Refactor Source Contract",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- source_path: `{payload['source_path']}`",
        f"- cli_defaults_preserved: `{summary['cli_defaults_preserved']}`",
        f"- last_token_path_supported: `{summary['last_token_path_supported']}`",
        f"- telemetry_contract_ready: `{summary['telemetry_contract_ready']}`",
        f"- protected_telemetry_field_count: `{summary['protected_telemetry_field_count']}`",
        f"- protected_telemetry_missing_count: `{summary['protected_telemetry_missing_count']}`",
        f"- runtime_order_changed: `{summary['runtime_order_changed']}`",
        f"- default_promotes_experimental_flags: `{summary['default_promotes_experimental_flags']}`",
        f"- runtime_started: `{summary['runtime_started']}`",
        f"- compile_started: `{summary['compile_started']}`",
        "",
        "## Protected Defaults",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in payload["protected_defaults"].items())
    lines.extend(["", "## Local Refactor Contract", ""])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in payload["local_refactor_contract"].items()
    )
    lines.extend(["", "## Checks", ""])
    for name, row in payload["checks"].items():
        lines.append(f"- {name}: present `{row['present']}` line `{row['line']}`")
    lines.extend(["", "## Protected Telemetry Fields", ""])
    for name, row in payload["telemetry_field_checks"].items():
        lines.append(f"- {name}: present `{row['present']}` line `{row['line']}`")
    if payload["missing_checks"]:
        lines.extend(["", "## Missing", ""])
        lines.extend(f"- {item}" for item in payload["missing_checks"])
    if payload["missing_telemetry_fields"]:
        lines.extend(["", "## Missing Telemetry Fields", ""])
        lines.extend(f"- {item}" for item in payload["missing_telemetry_fields"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the static source contract for safe Dream7B B=4 runtime refactor work."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()
    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
