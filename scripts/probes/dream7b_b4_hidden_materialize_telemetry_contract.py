#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_b4_hidden_materialize_telemetry_contract"
DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_SOURCE = Path("scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py")
DEFAULT_DESIGN = (
    DEFAULT_ROOT / "dream7b_b4_hidden_materialize_design_contract_20260622.json"
)
DEFAULT_OUT_JSON = (
    DEFAULT_ROOT / "dream7b_b4_hidden_materialize_telemetry_contract_20260622.json"
)
DEFAULT_OUT_MD = (
    DEFAULT_ROOT / "dream7b_b4_hidden_materialize_telemetry_contract_20260622.md"
)


REQUIRED_FIELD_TOKENS = {
    "output_quant_scale_none_count": '"output_quant_scale_none_count":',
    "output_dtype_counts": '"output_dtype_counts":',
    "output_dtype_by_segment": '"output_dtype_by_segment":',
    "output_c_contiguous_count": '"output_c_contiguous_count":',
    "output_c_contiguous_by_segment": '"output_c_contiguous_by_segment":',
    "hidden_materialize_candidate_mode_counts": '"hidden_materialize_candidate_mode_counts":',
    "hidden_materialize_candidate_mode_by_segment": '"hidden_materialize_candidate_mode_by_segment":',
}

REQUIRED_MODE_TOKENS = {
    "final_logits_no_hidden_materialize": '"final_logits_no_hidden_materialize"',
    "preallocated_reusable_copy_or_scale": '"preallocated_reusable_copy_or_scale"',
    "scaled_output_materialize_multiply": '"scaled_output_materialize_multiply"',
    "scale_none_float32_c_contiguous_no_copy_candidate": (
        '"scale_none_float32_c_contiguous_no_copy_candidate"'
    ),
    "scale_none_materialize_copy": '"scale_none_materialize_copy"',
}

BEHAVIOR_TOKENS = {
    "copyto_reusable_path": 'np.copyto(reusable, arr, casting="unsafe")',
    "multiply_reusable_path": 'np.multiply(arr, float(scale), out=reusable, casting="unsafe")',
    "copy_true_no_reusable_path": "result = arr.astype(np.float32, copy=True)",
    "scaled_no_reusable_path": "result = arr.astype(np.float32, copy=False) * float(scale)",
    "preallocate_hidden_default_off": 'parser.add_argument("--preallocate-hidden", action="store_true")',
    "prewarm_hbm_default_off": 'parser.add_argument("--prewarm-hbm", action="store_true"',
    "final_logits_mode_default_full": 'default="full"',
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_line(lines: list[str], token: str) -> int | None:
    for lineno, line in enumerate(lines, start=1):
        if token in line:
            return lineno
    return None


def locate_tokens(lines: list[str], tokens: dict[str, str]) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for name, token in tokens.items():
        line = find_line(lines, token)
        refs[name] = {
            "token": token,
            "line": line,
            "present": line is not None,
        }
    return refs


def missing(refs: dict[str, dict[str, Any]]) -> list[str]:
    return [name for name, ref in refs.items() if ref.get("present") is not True]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    lines = args.source.read_text(encoding="utf-8").splitlines()
    design = read_json(args.design_json)
    design_summary = design.get("summary") or {}
    design_decision = design.get("decision") or {}

    helper_tokens = {
        "candidate_mode_helper": "def hidden_materialize_candidate_mode(",
        "output_telemetry_helper": "def output_telemetry_fields(",
        "count_value_helper": "def count_value(",
        "merge_counts_helper": "def merge_counts(",
        "telemetry_insert_microbatch": "**telemetry,",
        "telemetry_insert_segment_major": '"hidden_materialize_candidate_mode": hidden_candidate_mode,',
        "markdown_output_dtype_counts": "f\"- output_dtype_counts:",
    }
    helper_refs = locate_tokens(lines, helper_tokens)
    field_refs = locate_tokens(lines, REQUIRED_FIELD_TOKENS)
    mode_refs = locate_tokens(lines, REQUIRED_MODE_TOKENS)
    behavior_refs = locate_tokens(lines, BEHAVIOR_TOKENS)

    missing_helpers = missing(helper_refs)
    missing_fields = missing(field_refs)
    missing_modes = missing(mode_refs)
    missing_behavior = missing(behavior_refs)
    failed_checks = []
    checks = {
        "design_contract_ok": design.get("verdict")
        == "ok_dream7b_b4_hidden_materialize_design_contract"
        and not (design.get("failed_checks") or []),
        "design_contract_asked_for_report_only_telemetry": design_summary.get(
            "next_report_only_item"
        )
        == "hidden_materialize_telemetry_only"
        and design_decision.get("allow_report_only_source_contract_followup_now")
        is True,
        "helpers_present": not missing_helpers,
        "required_telemetry_fields_present": not missing_fields,
        "candidate_modes_present": not missing_modes,
        "materialize_behavior_paths_preserved": not missing_behavior,
        "current_preallocate_hidden_still_rejected": design_summary.get(
            "current_preallocate_hidden_rejected"
        )
        is True,
        "defaults_not_promoted": design_summary.get(
            "default_runtime_change_allowed_now"
        )
        is False
        and design_decision.get("promote_current_preallocate_hidden") is False,
        "runtime_compile_not_started": True,
    }
    failed_checks = [key for key, value in checks.items() if not value]

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "tool_id": TOOL_ID,
        "verdict": "ok_dream7b_b4_hidden_materialize_telemetry_contract"
        if not failed_checks
        else "failed_dream7b_b4_hidden_materialize_telemetry_contract",
        "scope": "source-only hidden-materialize telemetry contract; no runtime or compile execution",
        "source_paths": {
            "runtime_source": str(args.source),
            "hidden_materialize_design_contract": str(args.design_json),
        },
        "summary": {
            "helper_count": len(helper_refs),
            "missing_helper_count": len(missing_helpers),
            "required_telemetry_field_count": len(field_refs),
            "missing_telemetry_field_count": len(missing_fields),
            "candidate_mode_count": len(mode_refs),
            "missing_candidate_mode_count": len(missing_modes),
            "behavior_token_count": len(behavior_refs),
            "missing_behavior_token_count": len(missing_behavior),
            "source_anchor_missing_count": (
                len(missing_helpers)
                + len(missing_fields)
                + len(missing_modes)
                + len(missing_behavior)
            ),
            "current_preallocate_hidden_rejected": design_summary.get(
                "current_preallocate_hidden_rejected"
            ),
            "next_design_only_item": design_summary.get("next_design_only_item"),
            "next_report_only_item": design_summary.get("next_report_only_item"),
            "default_runtime_change_allowed_now": False,
            "s100p_runtime_experiment_allowed_now": False,
            "compile_start_allowed_now": False,
            "runtime_started": False,
            "compile_started": False,
            "remote_access_performed": False,
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "missing": {
            "helpers": missing_helpers,
            "telemetry_fields": missing_fields,
            "candidate_modes": missing_modes,
            "behavior_tokens": missing_behavior,
        },
        "source_refs": {
            "helpers": helper_refs,
            "telemetry_fields": field_refs,
            "candidate_modes": mode_refs,
            "behavior_tokens": behavior_refs,
        },
        "decision": {
            "telemetry_source_ready": not failed_checks,
            "deploy_or_run_now": False,
            "change_runtime_defaults_now": False,
            "start_s100p_runtime_now": False,
            "start_compile_now": False,
            "next_evidence_gate": "run one existing B=4 telemetry command later to populate scale/dtype/contiguity fields",
        },
        "audit": {
            "runtime_source_modified_for_telemetry_only": True,
            "default_behavior_changed": False,
            "runtime_started": False,
            "compile_started": False,
            "remote_access_performed": False,
            "service_restarted": False,
            "local_writes": "JSON/Markdown source telemetry contract only",
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B=4 Hidden Materialize Telemetry Contract",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- helper_count: `{summary['helper_count']}`",
        f"- required_telemetry_field_count: `{summary['required_telemetry_field_count']}`",
        f"- candidate_mode_count: `{summary['candidate_mode_count']}`",
        f"- behavior_token_count: `{summary['behavior_token_count']}`",
        f"- source_anchor_missing_count: `{summary['source_anchor_missing_count']}`",
        f"- current_preallocate_hidden_rejected: `{summary['current_preallocate_hidden_rejected']}`",
        f"- next_design_only_item: `{summary['next_design_only_item']}`",
        f"- next_report_only_item: `{summary['next_report_only_item']}`",
        f"- default_runtime_change_allowed_now: `{summary['default_runtime_change_allowed_now']}`",
        f"- s100p_runtime_experiment_allowed_now: `{summary['s100p_runtime_experiment_allowed_now']}`",
        f"- compile_start_allowed_now: `{summary['compile_start_allowed_now']}`",
        f"- telemetry_source_ready: `{decision['telemetry_source_ready']}`",
        f"- next_evidence_gate: `{decision['next_evidence_gate']}`",
        "",
        "## Missing",
        "",
    ]
    for key, values in payload["missing"].items():
        lines.append(f"- {key}: `{values}`")
    lines.extend(
        [
            "",
            "## Audit",
            "",
            f"- runtime_source_modified_for_telemetry_only: `{payload['audit']['runtime_source_modified_for_telemetry_only']}`",
            f"- default_behavior_changed: `{payload['audit']['default_behavior_changed']}`",
            f"- runtime_started: `{payload['audit']['runtime_started']}`",
            f"- compile_started: `{payload['audit']['compile_started']}`",
            f"- remote_access_performed: `{payload['audit']['remote_access_performed']}`",
            f"- failed_checks: `{payload['failed_checks']}`",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--design-json", type=Path, default=DEFAULT_DESIGN)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.out_md.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"verdict": payload["verdict"], "json": str(args.out_json), "md": str(args.out_md)}, indent=2))


if __name__ == "__main__":
    main()
