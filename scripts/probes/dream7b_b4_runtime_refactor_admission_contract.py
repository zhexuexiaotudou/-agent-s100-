#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_b4_runtime_refactor_admission_contract"
DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_BACKLOG = DEFAULT_ROOT / "dream7b_b4_runtime_refactor_backlog_20260621.json"
DEFAULT_SOURCE_CONTRACT = (
    DEFAULT_ROOT / "dream7b_b4_runtime_refactor_source_contract_20260621.json"
)
DEFAULT_RUNTIME_GATE = DEFAULT_ROOT / "dream7b_b4_runtime_experiment_gate_20260620.json"
DEFAULT_RUNTIME_GUARD = DEFAULT_ROOT / "dream7b_b4_runtime_command_guard_20260621.json"
DEFAULT_COMPILE_GUARD = DEFAULT_ROOT / "dream7b_b4_compile_command_guard_20260621.json"
DEFAULT_NEXT_ACTION_PACK = DEFAULT_ROOT / "dream7b_b4_next_action_admission_pack_20260621.json"
DEFAULT_TUNING_MATRIX = DEFAULT_ROOT / "dream7b_b4_tuning_decision_matrix_20260621.json"
DEFAULT_VALIDATION_PLAN = (
    DEFAULT_ROOT / "dream7b_b4_last_token_runtime_validation_plan_20260620.json"
)
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_runtime_refactor_admission_contract_20260621.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_runtime_refactor_admission_contract_20260621.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_true(value: Any) -> bool:
    return value is True


def backlog_item(backlog: dict[str, Any], item_id: str) -> dict[str, Any]:
    for item in backlog.get("backlog") or []:
        if item.get("id") == item_id:
            return item
    return {}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    backlog = read_json(args.backlog_json)
    source_contract = read_json(args.source_contract_json)
    runtime_gate = read_json(args.runtime_gate_json)
    runtime_guard = read_json(args.runtime_guard_json)
    compile_guard = read_json(args.compile_guard_json)
    next_pack = read_json(args.next_action_pack_json)
    tuning_matrix = read_json(args.tuning_matrix_json)
    validation_plan = read_json(args.validation_plan_json)

    backlog_decision = backlog.get("decision") or {}
    source_summary = source_contract.get("summary") or {}
    source_local = source_contract.get("local_refactor_contract") or {}
    runtime_decision = runtime_gate.get("decision") or {}
    runtime_guard_summary = runtime_guard.get("guard") or {}
    compile_guard_summary = compile_guard.get("guard") or {}
    next_summary = next_pack.get("summary") or {}
    next_decision = next_pack.get("decision") or {}
    tuning_decision = tuning_matrix.get("decision") or {}
    validation_ready = (validation_plan.get("readiness") or {}).get("validation_ready") is True

    protected_telemetry_ready = (
        source_summary.get("protected_telemetry_fields_ready") is True
        and int(source_summary.get("protected_telemetry_field_count") or 0) >= 22
        and int(source_summary.get("protected_telemetry_missing_count") or 0) == 0
    )
    defaults_safe = (
        source_summary.get("cli_defaults_preserved") is True
        and source_summary.get("runtime_order_changed") is False
        and source_summary.get("default_promotes_experimental_flags") is False
    )
    runtime_blocked = (
        runtime_decision.get("s100p_runtime_experiment_now") is False
        and runtime_guard_summary.get("would_start_runtime") is False
    )
    compile_blocked = compile_guard_summary.get("would_start_compile") is False
    queue_default = (
        backlog_decision.get("queue_batch_remains_default") is True
        and runtime_decision.get("queue_batch_service_remains_default") is True
    )

    final_logits_item = backlog_item(backlog, "final_logits_last_token_path")
    hidden_item = backlog_item(backlog, "alternative_hidden_materialize_avoidance")
    loop_item = backlog_item(backlog, "segment_loop_bookkeeping")
    group_item = backlog_item(backlog, "group_switch_release_gc")
    cache_item = backlog_item(backlog, "hbm_prewarm_or_io_cache")

    admission_rows = [
        {
            "id": "report_only_instrumentation_and_contract_updates",
            "category": "local_report_only",
            "admitted_now": protected_telemetry_ready and defaults_safe,
            "would_start_runtime": False,
            "would_start_compile": False,
            "default_behavior_change_allowed": False,
            "reason": "source contract protects the 22 telemetry fields and preserves CLI/runtime defaults",
            "required_evidence_before_promotion": [
                "protected_telemetry_missing_count remains 0",
                "runtime_order_changed remains false",
                "default_promotes_experimental_flags remains false",
            ],
        },
        {
            "id": "seg27_28_last_token_path",
            "category": "future_runtime_candidate",
            "admitted_now": False,
            "would_start_runtime": False,
            "would_start_compile": False,
            "default_behavior_change_allowed": False,
            "projected_saved_ms_per_request": final_logits_item.get(
                "projected_saved_ms_per_request"
            ),
            "blocked_by": [
                "last_token_compile_not_ready",
                "last_token_manifest_not_ready",
                "last_token_runtime_validation_not_ready",
            ],
            "reason": "highest-value code target, but it needs the single-segment last-token HBM manifest and mb512 validation before runtime admission",
            "required_evidence_before_promotion": final_logits_item.get("acceptance") or [],
        },
        {
            "id": "alternative_hidden_materialize_avoidance",
            "category": "design_only",
            "admitted_now": bool(
                source_local.get("hidden_materialize_can_be_measured_before_any_promotion")
            ),
            "would_start_runtime": False,
            "would_start_compile": False,
            "default_behavior_change_allowed": False,
            "ceiling_ms_per_request": hidden_item.get("expected_ceiling_ms_per_request"),
            "reason": "current preallocate-hidden implementation is measured slower; only a different design can be investigated locally without changing defaults",
            "required_evidence_before_promotion": hidden_item.get("acceptance") or [],
        },
        {
            "id": "segment_loop_bookkeeping",
            "category": "defer_broad_rewrite",
            "admitted_now": False,
            "would_start_runtime": False,
            "would_start_compile": False,
            "default_behavior_change_allowed": False,
            "ceiling_ms_per_request": loop_item.get("expected_ceiling_ms_per_request"),
            "reason": "loop bookkeeping is below final-logits leverage and should wait until the active path changes",
            "required_evidence_before_promotion": loop_item.get("acceptance") or [],
        },
        {
            "id": "group_switch_release_gc_or_more_partitions",
            "category": "blocked_duplicate_or_low_value_sweep",
            "admitted_now": False,
            "would_start_runtime": False,
            "would_start_compile": False,
            "default_behavior_change_allowed": False,
            "ceiling_ms_per_request": group_item.get("expected_ceiling_ms_per_request"),
            "reason": "group/order variants did not beat the baseline and standard sweeps are already covered by NAS/local inventory",
            "required_evidence_before_promotion": group_item.get("acceptance") or [],
        },
        {
            "id": "hbm_prewarm_or_io_cache_default",
            "category": "blocked_negative_or_memory_plan_dependent",
            "admitted_now": False,
            "would_start_runtime": False,
            "would_start_compile": False,
            "default_behavior_change_allowed": False,
            "ceiling_ms_per_request": cache_item.get("expected_ceiling_ms_per_request"),
            "reason": "prewarm/cache must stay off by default until a memory-residency plan changes the active profile",
            "required_evidence_before_promotion": cache_item.get("acceptance") or [],
        },
        {
            "id": "compile_preflight_only",
            "category": "preflight_only",
            "admitted_now": next_decision.get("compile_preflight_only_allowed_now") is True,
            "would_start_runtime": False,
            "would_start_compile": False,
            "default_behavior_change_allowed": False,
            "safe_command": next_summary.get("safe_compile_preflight_command"),
            "reason": "preflight-only command is allowed as evidence gathering; actual compile remains blocked by readiness/capacity",
            "required_evidence_before_promotion": [
                "compile_ready true",
                "capacity plan no longer blocks compile",
                "remote last-token manifest absent or intentionally overwritten",
            ],
        },
    ]

    allowed_now = [row["id"] for row in admission_rows if row["admitted_now"]]
    blocked_runtime = [
        row["id"]
        for row in admission_rows
        if row.get("category") in {"future_runtime_candidate", "blocked_duplicate_or_low_value_sweep"}
        and not row["admitted_now"]
    ]

    checks = {
        "backlog_ok": backlog.get("verdict") == "ok_dream7b_b4_runtime_refactor_backlog",
        "source_contract_ok": source_contract.get("verdict")
        == "ok_dream7b_b4_runtime_refactor_source_contract",
        "protected_telemetry_ready": protected_telemetry_ready,
        "defaults_safe": defaults_safe,
        "runtime_gate_blocks_s100p": runtime_blocked,
        "compile_guard_blocks_compile": compile_blocked,
        "next_action_pack_starts_no_runtime_or_compile": next_summary.get("would_start_runtime")
        is False
        and next_summary.get("would_start_compile") is False,
        "queue_batch_default": queue_default,
        "tuning_blocks_standard_sweeps": tuning_decision.get(
            "standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage"
        )
        is True,
        "last_token_validation_not_ready": validation_ready is False,
    }
    failed_checks = [key for key, value in checks.items() if not value]
    verdict = (
        "ok_dream7b_b4_runtime_refactor_admission_contract"
        if not failed_checks
        else "failed_dream7b_b4_runtime_refactor_admission_contract"
    )

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "source_paths": {
            "backlog": str(args.backlog_json),
            "source_contract": str(args.source_contract_json),
            "runtime_gate": str(args.runtime_gate_json),
            "runtime_guard": str(args.runtime_guard_json),
            "compile_guard": str(args.compile_guard_json),
            "next_action_pack": str(args.next_action_pack_json),
            "tuning_matrix": str(args.tuning_matrix_json),
            "validation_plan": str(args.validation_plan_json),
        },
        "summary": {
            "queue_batch_remains_default": queue_default,
            "default_runtime_code_change_allowed_now": False,
            "local_report_only_refactor_allowed_now": (
                "report_only_instrumentation_and_contract_updates" in allowed_now
            ),
            "design_only_hidden_materialize_allowed_now": (
                "alternative_hidden_materialize_avoidance" in allowed_now
            ),
            "s100p_runtime_experiment_allowed_now": False,
            "compile_start_allowed_now": False,
            "compile_preflight_only_allowed_now": (
                "compile_preflight_only" in allowed_now
            ),
            "protected_telemetry_field_count": source_summary.get(
                "protected_telemetry_field_count"
            ),
            "protected_telemetry_missing_count": source_summary.get(
                "protected_telemetry_missing_count"
            ),
            "primary_runtime_refactor_target": backlog_decision.get(
                "primary_runtime_refactor_target"
            ),
            "next_runtime_candidate": runtime_decision.get(
                "next_nonduplicate_runtime_candidate"
            ),
            "only_future_runtime_candidate": next_decision.get(
                "only_future_runtime_candidate"
            ),
            "allowed_now_count": len(allowed_now),
            "runtime_blocked_candidate_count": len(blocked_runtime),
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "admission_rows": admission_rows,
        "decision": {
            "admit_local_report_only_refactor_now": (
                "report_only_instrumentation_and_contract_updates" in allowed_now
            ),
            "admit_default_runtime_behavior_change_now": False,
            "admit_s100p_runtime_now": False,
            "admit_compile_start_now": False,
            "admit_compile_preflight_only_now": (
                "compile_preflight_only" in allowed_now
            ),
            "keep_queue_batch_default": queue_default,
            "keep_5_group_segment_major_as_b4_analysis_baseline": True,
            "block_standard_group_or_inner_order_sweeps": True,
            "block_prewarm_or_cache_default": True,
            "next_required_external_state_change": "last-token manifest verification after local compile readiness/capacity passes",
        },
        "audit": {
            "runtime_started": False,
            "compile_started": False,
            "service_restarted": False,
            "remote_access_performed": False,
            "local_writes": "JSON/Markdown runtime refactor admission contract only",
        },
    }


def render_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Dream7B B=4 Runtime Refactor Admission Contract",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- queue_batch_remains_default: `{summary['queue_batch_remains_default']}`",
        f"- local_report_only_refactor_allowed_now: `{summary['local_report_only_refactor_allowed_now']}`",
        f"- design_only_hidden_materialize_allowed_now: `{summary['design_only_hidden_materialize_allowed_now']}`",
        f"- default_runtime_code_change_allowed_now: `{summary['default_runtime_code_change_allowed_now']}`",
        f"- s100p_runtime_experiment_allowed_now: `{summary['s100p_runtime_experiment_allowed_now']}`",
        f"- compile_start_allowed_now: `{summary['compile_start_allowed_now']}`",
        f"- compile_preflight_only_allowed_now: `{summary['compile_preflight_only_allowed_now']}`",
        f"- protected_telemetry_field_count: `{summary['protected_telemetry_field_count']}`",
        f"- protected_telemetry_missing_count: `{summary['protected_telemetry_missing_count']}`",
        f"- primary_runtime_refactor_target: `{summary['primary_runtime_refactor_target']}`",
        f"- only_future_runtime_candidate: `{summary['only_future_runtime_candidate']}`",
        "",
        "## Admission Rows",
        "",
        "| id | category | admitted now | runtime | compile | default change | reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["admission_rows"]:
        lines.append(
            f"| {row['id']} | {row['category']} | {row['admitted_now']} | "
            f"{row['would_start_runtime']} | {row['would_start_compile']} | "
            f"{row['default_behavior_change_allowed']} | {row['reason']} |"
        )
    lines.extend(["", "## Checks", ""])
    for key, value in payload["checks"].items():
        lines.append(f"- {key}: `{value}`")
    if payload["failed_checks"]:
        lines.extend(["", "## Failed Checks", ""])
        lines.extend(f"- {item}" for item in payload["failed_checks"])
    lines.extend(["", "## Source Paths", ""])
    for key, value in payload["source_paths"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gate Dream7B B=4 runtime scheduling/refactor changes from existing evidence only."
    )
    parser.add_argument("--backlog-json", type=Path, default=DEFAULT_BACKLOG)
    parser.add_argument("--source-contract-json", type=Path, default=DEFAULT_SOURCE_CONTRACT)
    parser.add_argument("--runtime-gate-json", type=Path, default=DEFAULT_RUNTIME_GATE)
    parser.add_argument("--runtime-guard-json", type=Path, default=DEFAULT_RUNTIME_GUARD)
    parser.add_argument("--compile-guard-json", type=Path, default=DEFAULT_COMPILE_GUARD)
    parser.add_argument("--next-action-pack-json", type=Path, default=DEFAULT_NEXT_ACTION_PACK)
    parser.add_argument("--tuning-matrix-json", type=Path, default=DEFAULT_TUNING_MATRIX)
    parser.add_argument("--validation-plan-json", type=Path, default=DEFAULT_VALIDATION_PLAN)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()
    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_markdown(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
