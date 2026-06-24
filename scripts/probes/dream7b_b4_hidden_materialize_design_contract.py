#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_b4_hidden_materialize_design_contract"
DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_SOURCE = Path("scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py")
DEFAULT_OVERHEAD = (
    DEFAULT_ROOT / "dream7b_b4_post_instrumentation_overhead_analysis_20260621.json"
)
DEFAULT_HIDDEN_REUSE = DEFAULT_ROOT / "dream7b_b4_hidden_buffer_reuse_decision_20260621.json"
DEFAULT_SOURCE_CONTRACT = (
    DEFAULT_ROOT / "dream7b_b4_runtime_refactor_source_contract_20260621.json"
)
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_hidden_materialize_design_contract_20260622.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_hidden_materialize_design_contract_20260622.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_line(lines: list[str], needle: str) -> int | None:
    for lineno, line in enumerate(lines, start=1):
        if needle in line:
            return lineno
    return None


def source_refs(lines: list[str], tokens: dict[str, str]) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for name, token in tokens.items():
        line = find_line(lines, token)
        refs[name] = {
            "token": token,
            "present": line is not None,
            "line": line,
        }
    return refs


def missing_refs(refs: dict[str, dict[str, Any]]) -> list[str]:
    return [name for name, row in refs.items() if row.get("present") is not True]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    lines = args.source.read_text(encoding="utf-8").splitlines()
    overhead = read_json(args.overhead_json)
    hidden_reuse = read_json(args.hidden_reuse_json)
    source_contract = read_json(args.source_contract_json)
    totals = overhead.get("totals") or {}
    overhead_decision = overhead.get("decision") or {}
    hidden_decision = hidden_reuse.get("decision") or {}
    hidden_delta = hidden_reuse.get("latest_prealloc_ab_delta") or {}
    source_local = source_contract.get("local_refactor_contract") or {}

    refs = source_refs(
        lines,
        {
            "materialize_hidden_def": "def materialize_hidden(",
            "copyto_reusable": 'np.copyto(reusable, arr, casting="unsafe")',
            "multiply_reusable": 'np.multiply(arr, float(scale), out=reusable, casting="unsafe")',
            "astype_copy_true": "result = arr.astype(np.float32, copy=True)",
            "astype_copy_false_scaled": "result = arr.astype(np.float32, copy=False) * float(scale)",
            "preallocate_hidden_arg": 'parser.add_argument("--preallocate-hidden", action="store_true")',
            "hidden_buffers_alloc": "hidden_buffers = [",
            "hidden_materialize_metric": '"hidden_materialize_ms": round(sum(materialize_times), 3),',
            "reused_hidden_buffer_count_metric": '"reused_hidden_buffer_count": reused_buffer_count,',
        },
    )

    current_reuse_slower = hidden_decision.get("reuse_buffer_implementation_measured_slower") is True
    current_reuse_default = hidden_decision.get("hidden_buffer_reuse_default") is True
    prealloc_delta = hidden_delta.get("ms_per_request_delta")
    hidden_delta_ms = hidden_delta.get("hidden_materialize_ms_per_request_delta")
    hidden_ms_per_request = totals.get("hidden_materialize_ms_per_request")
    final_excess = totals.get("final_excess_ms_per_request_vs_hidden")
    hidden_to_final_ratio = (
        None
        if not hidden_ms_per_request or not final_excess
        else round(float(hidden_ms_per_request) / float(final_excess), 6)
    )

    design_rows = [
        {
            "id": "current_preallocate_hidden_copyto_path",
            "status": "rejected_by_measurement",
            "allowed_now": False,
            "default_behavior_change_allowed": False,
            "reason": "the current reusable-buffer branch uses copyto/multiply(out=...) and the mb512 A/B was slower",
            "evidence": {
                "ms_per_request_delta": prealloc_delta,
                "hidden_materialize_ms_per_request_delta": hidden_delta_ms,
                "reused_hidden_buffer_count": hidden_delta.get("reused_hidden_buffer_count"),
            },
            "acceptance_before_reconsidering": [
                "candidate is not the current copyto/multiply(out=...) implementation",
                "mb512 A/B beats no-prealloc baseline",
                "nonzero BPU does not regress by more than 0.5 points",
            ],
        },
        {
            "id": "scale_none_no_copy_handoff",
            "status": "design_only_needs_scale_dtype_aliasing_telemetry",
            "allowed_now": True,
            "default_behavior_change_allowed": False,
            "reason": "only a no-copy handoff for already-float32 unscaled hidden tensors could avoid materialization without repeating the slower reusable-buffer path",
            "required_source_or_telemetry_before_code": [
                "per-segment output_quant_scale None/non-None counts",
                "arr dtype and contiguity counters",
                "proof downstream runtime does not mutate hidden input",
                "explicit experimental flag, default off",
            ],
            "acceptance_before_promotion": [
                "hidden_materialize_ms_per_item is still reported",
                "reused_hidden_buffer_count remains meaningful",
                "mb512 A/B improves wall time by at least 0.5 ms/request",
                "final logits remains separately attributed",
            ],
        },
        {
            "id": "scaled_hidden_dequantize_alternative",
            "status": "blocked_until_non_copyto_design_exists",
            "allowed_now": False,
            "default_behavior_change_allowed": False,
            "reason": "scaled outputs currently require float32 materialization; the measured reusable-buffer multiply path did not help",
            "required_source_or_telemetry_before_code": [
                "runtime API evidence for consuming quantized output plus scale, or a different dequantize path",
                "per-segment scale distribution",
                "explicit telemetry separating dequantize time from output postprocess",
            ],
        },
        {
            "id": "hidden_materialize_telemetry_only",
            "status": "report_only_allowed",
            "allowed_now": True,
            "default_behavior_change_allowed": False,
            "reason": "additional local source-contract/report fields can sharpen the design without running S100P",
            "required_fields": [
                "output_quant_scale_none_count",
                "output_dtype_by_segment",
                "output_c_contiguous_by_segment",
                "hidden_materialize_candidate_mode",
            ],
        },
        {
            "id": "final_logits_first_policy",
            "status": "keep_hidden_materialize_secondary",
            "allowed_now": False,
            "default_behavior_change_allowed": False,
            "reason": "hidden materialize is a smaller secondary ceiling while final logits remains the stable primary bottleneck",
            "evidence": {
                "hidden_materialize_ms_per_request": hidden_ms_per_request,
                "final_excess_ms_per_request_vs_hidden": final_excess,
                "hidden_to_final_excess_ratio": hidden_to_final_ratio,
                "final_logits_compute_still_primary": overhead_decision.get(
                    "final_logits_compute_still_primary"
                ),
            },
        },
    ]

    failed_checks = []
    checks = {
        "overhead_report_ok": overhead.get("verdict")
        == "ok_dream7b_b4_post_instrumentation_overhead_analysis",
        "hidden_reuse_decision_ok": hidden_reuse.get("verdict")
        == "ok_dream7b_b4_hidden_buffer_reuse_decision",
        "source_contract_ok": source_contract.get("verdict")
        == "ok_dream7b_b4_runtime_refactor_source_contract",
        "materialize_source_anchors_present": not missing_refs(refs),
        "current_preallocate_hidden_rejected": current_reuse_slower
        and hidden_decision.get("preallocate_hidden_experimental_flag_only") is True
        and hidden_decision.get("do_not_change_runtime_defaults_now") is True
        and current_reuse_default is False,
        "hidden_materialize_has_measured_ceiling": hidden_decision.get(
            "hidden_materialize_has_measured_ceiling"
        )
        is True
        and float(hidden_ms_per_request or 0.0) > 0.0,
        "final_logits_remains_primary": hidden_decision.get(
            "primary_target_remains_final_logits"
        )
        is True
        and overhead_decision.get("final_logits_compute_still_primary") is True,
        "local_design_allowed_without_runtime": source_local.get(
            "hidden_materialize_can_be_measured_before_any_promotion"
        )
        is True,
        "default_runtime_change_blocked": True,
        "runtime_compile_not_started": True,
    }
    failed_checks = [key for key, value in checks.items() if not value]

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "tool_id": TOOL_ID,
        "verdict": "ok_dream7b_b4_hidden_materialize_design_contract"
        if not failed_checks
        else "failed_dream7b_b4_hidden_materialize_design_contract",
        "scope": "local design contract for hidden materialize alternatives; no runtime/default changes",
        "source_paths": {
            "runtime_source": str(args.source),
            "post_instrumentation_overhead": str(args.overhead_json),
            "hidden_buffer_reuse_decision": str(args.hidden_reuse_json),
            "runtime_refactor_source_contract": str(args.source_contract_json),
        },
        "summary": {
            "design_row_count": len(design_rows),
            "allowed_design_only_count": sum(1 for row in design_rows if row["allowed_now"]),
            "source_anchor_missing_count": len(missing_refs(refs)),
            "hidden_materialize_ms_per_request": hidden_ms_per_request,
            "hidden_materialize_ms_per_item": totals.get("hidden_materialize_ms_per_item"),
            "prealloc_ms_per_request_delta": prealloc_delta,
            "prealloc_hidden_materialize_ms_per_request_delta": hidden_delta_ms,
            "current_preallocate_hidden_rejected": current_reuse_slower,
            "preallocate_hidden_experimental_flag_only": hidden_decision.get(
                "preallocate_hidden_experimental_flag_only"
            ),
            "hidden_materialize_has_measured_ceiling": hidden_decision.get(
                "hidden_materialize_has_measured_ceiling"
            ),
            "primary_target_remains_final_logits": hidden_decision.get(
                "primary_target_remains_final_logits"
            ),
            "hidden_to_final_excess_ratio": hidden_to_final_ratio,
            "next_design_only_item": "scale_none_no_copy_handoff",
            "next_report_only_item": "hidden_materialize_telemetry_only",
            "default_runtime_change_allowed_now": False,
            "s100p_runtime_experiment_allowed_now": False,
            "compile_start_allowed_now": False,
            "runtime_started": False,
            "compile_started": False,
            "remote_access_performed": False,
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "source_refs": refs,
        "design_rows": design_rows,
        "decision": {
            "allow_local_design_notes_now": True,
            "allow_report_only_source_contract_followup_now": True,
            "promote_current_preallocate_hidden": False,
            "change_runtime_defaults_now": False,
            "start_s100p_runtime_now": False,
            "start_compile_now": False,
            "keep_preallocate_hidden_explicit": True,
            "keep_queue_batch_default": True,
            "next_required_evidence": "scale/dtype/contiguity telemetry or a non-copyto design before any hidden-materialize runtime A/B",
        },
        "audit": {
            "source_modified": False,
            "runtime_started": False,
            "compile_started": False,
            "remote_access_performed": False,
            "service_restarted": False,
            "local_writes": "JSON/Markdown hidden materialize design contract only",
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B=4 Hidden Materialize Design Contract",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- design_row_count: `{summary['design_row_count']}`",
        f"- allowed_design_only_count: `{summary['allowed_design_only_count']}`",
        f"- source_anchor_missing_count: `{summary['source_anchor_missing_count']}`",
        f"- hidden_materialize_ms_per_request: `{summary['hidden_materialize_ms_per_request']}`",
        f"- prealloc_ms_per_request_delta: `{summary['prealloc_ms_per_request_delta']}`",
        f"- prealloc_hidden_materialize_ms_per_request_delta: `{summary['prealloc_hidden_materialize_ms_per_request_delta']}`",
        f"- current_preallocate_hidden_rejected: `{summary['current_preallocate_hidden_rejected']}`",
        f"- primary_target_remains_final_logits: `{summary['primary_target_remains_final_logits']}`",
        f"- default_runtime_change_allowed_now: `{summary['default_runtime_change_allowed_now']}`",
        f"- s100p_runtime_experiment_allowed_now: `{summary['s100p_runtime_experiment_allowed_now']}`",
        f"- compile_start_allowed_now: `{summary['compile_start_allowed_now']}`",
        f"- next_design_only_item: `{summary['next_design_only_item']}`",
        f"- next_report_only_item: `{summary['next_report_only_item']}`",
        f"- next_required_evidence: `{decision['next_required_evidence']}`",
        "",
        "## Design Rows",
        "",
    ]
    for row in payload["design_rows"]:
        lines.extend(
            [
                f"### {row['id']}",
                "",
                f"- status: `{row['status']}`",
                f"- allowed_now: `{row['allowed_now']}`",
                f"- default_behavior_change_allowed: `{row['default_behavior_change_allowed']}`",
                f"- reason: `{row['reason']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Audit",
            "",
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
    parser.add_argument("--overhead-json", type=Path, default=DEFAULT_OVERHEAD)
    parser.add_argument("--hidden-reuse-json", type=Path, default=DEFAULT_HIDDEN_REUSE)
    parser.add_argument("--source-contract-json", type=Path, default=DEFAULT_SOURCE_CONTRACT)
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
