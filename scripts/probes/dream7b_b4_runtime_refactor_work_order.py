#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_b4_runtime_refactor_work_order"
DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_SOURCE = Path("scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py")
DEFAULT_BACKLOG = DEFAULT_ROOT / "dream7b_b4_runtime_refactor_backlog_20260621.json"
DEFAULT_SOURCE_CONTRACT = (
    DEFAULT_ROOT / "dream7b_b4_runtime_refactor_source_contract_20260621.json"
)
DEFAULT_IMPL_MAP = DEFAULT_ROOT / "dream7b_b4_runtime_source_implementation_map_20260621.json"
DEFAULT_ADMISSION = (
    DEFAULT_ROOT / "dream7b_b4_runtime_refactor_admission_contract_20260621.json"
)
DEFAULT_PER_RUN = DEFAULT_ROOT / "dream7b_b4_per_run_evidence_matrix_20260622.json"
DEFAULT_HIDDEN_DESIGN = (
    DEFAULT_ROOT / "dream7b_b4_hidden_materialize_design_contract_20260622.json"
)
DEFAULT_HIDDEN_TELEMETRY = (
    DEFAULT_ROOT / "dream7b_b4_hidden_materialize_telemetry_contract_20260622.json"
)
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_runtime_refactor_work_order_20260622.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_runtime_refactor_work_order_20260622.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_line(lines: list[str], needle: str) -> int | None:
    for index, line in enumerate(lines, start=1):
        if needle in line:
            return index
    return None


def item_by_id(rows: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    for row in rows:
        if row.get("id") == item_id or row.get("implementation_area") == item_id:
            return row
    return {}


def source_anchor_status(
    *,
    lines: list[str],
    item: dict[str, Any],
    source_contract_checks: dict[str, Any],
) -> dict[str, Any]:
    anchors = []
    for anchor in item.get("source_anchors") or []:
        needle = str(anchor.get("needle") or "")
        recorded_line = anchor.get("line")
        current_line = find_line(lines, needle)
        anchors.append(
            {
                "file": anchor.get("file"),
                "needle": needle,
                "recorded_line": recorded_line,
                "current_line": current_line,
                "present": current_line is not None,
                "line_drift": (
                    None
                    if current_line is None or not isinstance(recorded_line, int)
                    else current_line - recorded_line
                ),
            }
        )

    contract_hits = []
    for name, check in source_contract_checks.items():
        token = str(check.get("token") or "")
        if not token:
            continue
        current_line = find_line(lines, token)
        contract_hits.append(
            {
                "name": name,
                "recorded_line": check.get("line"),
                "current_line": current_line,
                "present": current_line is not None,
            }
        )

    missing_anchors = [row for row in anchors if row["present"] is not True]
    drifting_anchors = [
        row
        for row in anchors
        if isinstance(row.get("line_drift"), int) and row["line_drift"] != 0
    ]
    return {
        "anchors": anchors,
        "source_anchor_count": len(anchors),
        "source_anchor_present_count": len(anchors) - len(missing_anchors),
        "source_anchors_all_present": not missing_anchors,
        "source_anchor_missing_count": len(missing_anchors),
        "source_anchor_line_drift_count": len(drifting_anchors),
        "contract_source_tokens_checked": len(contract_hits),
        "contract_source_tokens_missing": [
            row["name"] for row in contract_hits if row["present"] is not True
        ],
    }


def categorize_work(
    item: dict[str, Any],
    admission_row: dict[str, Any],
    impl_row: dict[str, Any],
) -> dict[str, Any]:
    item_id = item.get("id")
    if item_id == "final_logits_last_token_path":
        return {
            "work_type": "future_compile_runtime_candidate",
            "local_next_action": "keep source hooks verified; wait for seg27_28 last-token manifest before runtime validation",
            "allowed_now": False,
            "runtime_or_compile_required_before_measurement": True,
        }
    if item_id == "alternative_hidden_materialize_avoidance":
        return {
            "work_type": "local_design_only",
            "local_next_action": "draft a non-copyto hidden-materialize design and keep --preallocate-hidden experimental",
            "allowed_now": admission_row.get("admitted_now") is True
            or impl_row.get("allowed_now") is True,
            "runtime_or_compile_required_before_measurement": False,
        }
    if item_id == "segment_loop_bookkeeping":
        return {
            "work_type": "defer_broad_loop_rewrite",
            "local_next_action": "only preserve telemetry and readability-safe checks until final-logits path changes",
            "allowed_now": False,
            "runtime_or_compile_required_before_measurement": False,
        }
    if item_id == "group_switch_release_gc":
        return {
            "work_type": "blocked_low_value_scheduler_change",
            "local_next_action": "do not change release-gc or group policy defaults; keep accounting fields stable",
            "allowed_now": False,
            "runtime_or_compile_required_before_measurement": True,
        }
    if item_id == "hbm_prewarm_or_io_cache":
        return {
            "work_type": "blocked_negative_cache_or_prewarm_change",
            "local_next_action": "do not add cache/prewarm defaults without a memory-residency plan and explicit telemetry",
            "allowed_now": False,
            "runtime_or_compile_required_before_measurement": True,
        }
    return {
        "work_type": "unknown",
        "local_next_action": item.get("next_action"),
        "allowed_now": admission_row.get("admitted_now") is True
        or impl_row.get("allowed_now") is True,
        "runtime_or_compile_required_before_measurement": bool(
            impl_row.get("runtime_or_compile_required")
        ),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    lines = args.source.read_text(encoding="utf-8").splitlines()
    backlog = read_json(args.backlog_json)
    source_contract = read_json(args.source_contract_json)
    impl_map = read_json(args.implementation_map_json)
    admission = read_json(args.admission_json)
    per_run = read_json(args.per_run_matrix_json)
    hidden_design = read_json(args.hidden_materialize_design_json)
    hidden_telemetry = read_json(args.hidden_materialize_telemetry_json)

    source_summary = source_contract.get("summary") or {}
    source_checks = source_contract.get("checks") or {}
    backlog_decision = backlog.get("decision") or {}
    admission_summary = admission.get("summary") or {}
    admission_decision = admission.get("decision") or {}
    per_run_summary = per_run.get("summary") or {}
    per_run_findings = per_run.get("findings") or {}
    hidden_design_summary = hidden_design.get("summary") or {}
    hidden_design_decision = hidden_design.get("decision") or {}
    hidden_design_audit = hidden_design.get("audit") or {}
    hidden_telemetry_summary = hidden_telemetry.get("summary") or {}
    hidden_telemetry_decision = hidden_telemetry.get("decision") or {}
    hidden_telemetry_audit = hidden_telemetry.get("audit") or {}
    impl_summary = impl_map.get("summary") or {}
    impl_rows = impl_map.get("implementation_rows") or []
    admission_rows = admission.get("admission_rows") or []

    work_rows: list[dict[str, Any]] = []
    for item in backlog.get("backlog") or []:
        item_id = str(item.get("id"))
        admission_row = item_by_id(admission_rows, {
            "final_logits_last_token_path": "seg27_28_last_token_path",
            "group_switch_release_gc": "group_switch_release_gc_or_more_partitions",
            "hbm_prewarm_or_io_cache": "hbm_prewarm_or_io_cache_default",
        }.get(item_id, item_id))
        impl_row = item_by_id(
            impl_rows,
            {
                "final_logits_last_token_path": "seg27_28_last_token_logits_or_output_avoidance",
                "alternative_hidden_materialize_avoidance": "alternative_hidden_materialize_avoidance",
                "segment_loop_bookkeeping": "group_major_scheduling_loop",
                "group_switch_release_gc": "release_gc_and_group_switch_accounting",
                "hbm_prewarm_or_io_cache": "hbm_prewarm_or_io_cache",
            }.get(item_id, item_id),
        )
        anchors = source_anchor_status(
            lines=lines,
            item=item,
            source_contract_checks=source_checks,
        )
        category = categorize_work(item, admission_row, impl_row)
        evidence = item.get("evidence") or {}
        row = {
            "rank": item.get("rank"),
            "id": item_id,
            "status": item.get("status"),
            **category,
            "default_behavior_change_allowed_now": False,
            "source_anchors_all_present": anchors["source_anchors_all_present"],
            "source_anchor_count": anchors["source_anchor_count"],
            "source_anchor_missing_count": anchors["source_anchor_missing_count"],
            "source_anchor_line_drift_count": anchors[
                "source_anchor_line_drift_count"
            ],
            "source_anchors": anchors["anchors"],
            "expected_ceiling_ms_per_request": item.get(
                "expected_ceiling_ms_per_request"
            ),
            "projected_saved_ms_per_request": item.get(
                "projected_saved_ms_per_request"
            ),
            "evidence": {
                "final_excess_to_group_switch_gap": evidence.get(
                    "final_excess_to_group_switch_gap"
                ),
                "final_excess_to_intra_segment_gap": evidence.get(
                    "final_excess_to_intra_segment_gap"
                ),
                "hidden_materialize_ms_per_request": evidence.get(
                    "hidden_materialize_ms_per_request"
                ),
                "preallocate_hidden_ms_per_request_delta": evidence.get(
                    "preallocate_hidden_ms_per_request_delta"
                ),
                "group_release_and_unaccounted_gap_not_primary": evidence.get(
                    "group_release_and_unaccounted_gap_not_primary"
                ),
                "final_logits_leverage_verdict": evidence.get(
                    "final_logits_leverage_verdict"
                ),
                "projection_is_not_bpu_promotion_proof": evidence.get(
                    "projection_is_not_bpu_promotion_proof"
                ),
            },
            "acceptance": item.get("acceptance") or [],
        }
        if item_id == "alternative_hidden_materialize_avoidance":
            row.update(
                {
                    "hidden_materialize_design_contract_verdict": hidden_design.get(
                        "verdict"
                    ),
                    "hidden_materialize_design_allowed_design_only_count": (
                        hidden_design_summary.get("allowed_design_only_count")
                    ),
                    "hidden_materialize_design_current_preallocate_hidden_rejected": (
                        hidden_design_summary.get(
                            "current_preallocate_hidden_rejected"
                        )
                    ),
                    "hidden_materialize_design_next_design_only_item": (
                        hidden_design_summary.get("next_design_only_item")
                    ),
                    "hidden_materialize_design_next_report_only_item": (
                        hidden_design_summary.get("next_report_only_item")
                    ),
                    "hidden_materialize_telemetry_contract_verdict": (
                        hidden_telemetry.get("verdict")
                    ),
                    "hidden_materialize_telemetry_required_field_count": (
                        hidden_telemetry_summary.get(
                            "required_telemetry_field_count"
                        )
                    ),
                    "hidden_materialize_telemetry_source_anchor_missing_count": (
                        hidden_telemetry_summary.get("source_anchor_missing_count")
                    ),
                    "hidden_materialize_telemetry_source_ready": (
                        hidden_telemetry_decision.get("telemetry_source_ready")
                    ),
                }
            )
        work_rows.append(row)

    missing_anchor_rows = [
        row for row in work_rows if row["source_anchors_all_present"] is not True
    ]
    allowed_local_rows = [row for row in work_rows if row["allowed_now"] is True]
    future_runtime_rows = [
        row
        for row in work_rows
        if row["work_type"] == "future_compile_runtime_candidate"
    ]
    blocked_default_rows = [
        row for row in work_rows if row["default_behavior_change_allowed_now"] is False
    ]
    contract_missing_tokens = [
        name
        for name, check in source_checks.items()
        if find_line(lines, str(check.get("token") or "")) is None
    ]

    checks = {
        "backlog_ok": backlog.get("verdict") == "ok_dream7b_b4_runtime_refactor_backlog",
        "source_contract_ok": source_contract.get("verdict")
        == "ok_dream7b_b4_runtime_refactor_source_contract",
        "implementation_map_ok": impl_map.get("verdict")
        == "ok_dream7b_b4_runtime_source_implementation_map",
        "admission_contract_ok": admission.get("verdict")
        == "ok_dream7b_b4_runtime_refactor_admission_contract",
        "per_run_matrix_ok": per_run.get("verdict")
        == "ok_dream7b_b4_per_run_evidence_matrix",
        "hidden_materialize_design_contract_ok": hidden_design.get("verdict")
        == "ok_dream7b_b4_hidden_materialize_design_contract"
        and not (hidden_design.get("failed_checks") or [])
        and int(hidden_design_summary.get("source_anchor_missing_count") or 0) == 0
        and hidden_design_summary.get("current_preallocate_hidden_rejected") is True
        and hidden_design_summary.get("default_runtime_change_allowed_now") is False
        and hidden_design_summary.get("s100p_runtime_experiment_allowed_now") is False
        and hidden_design_summary.get("compile_start_allowed_now") is False
        and hidden_design_decision.get("promote_current_preallocate_hidden") is False
        and hidden_design_decision.get("change_runtime_defaults_now") is False
        and hidden_design_audit.get("runtime_started") is False
        and hidden_design_audit.get("compile_started") is False
        and hidden_design_audit.get("remote_access_performed") is False,
        "hidden_materialize_telemetry_contract_ok": hidden_telemetry.get("verdict")
        == "ok_dream7b_b4_hidden_materialize_telemetry_contract"
        and not (hidden_telemetry.get("failed_checks") or [])
        and int(hidden_telemetry_summary.get("source_anchor_missing_count") or 0)
        == 0
        and int(
            hidden_telemetry_summary.get("required_telemetry_field_count") or 0
        )
        >= 7
        and hidden_telemetry_summary.get("current_preallocate_hidden_rejected")
        is True
        and hidden_telemetry_summary.get("default_runtime_change_allowed_now")
        is False
        and hidden_telemetry_summary.get("s100p_runtime_experiment_allowed_now")
        is False
        and hidden_telemetry_summary.get("compile_start_allowed_now") is False
        and hidden_telemetry_decision.get("telemetry_source_ready") is True
        and hidden_telemetry_decision.get("deploy_or_run_now") is False
        and hidden_telemetry_decision.get("change_runtime_defaults_now") is False
        and hidden_telemetry_audit.get("default_behavior_changed") is False
        and hidden_telemetry_audit.get("runtime_started") is False
        and hidden_telemetry_audit.get("compile_started") is False
        and hidden_telemetry_audit.get("remote_access_performed") is False,
        "source_anchors_all_present": not missing_anchor_rows,
        "source_contract_tokens_all_present": not contract_missing_tokens,
        "queue_batch_default_preserved": backlog_decision.get(
            "queue_batch_remains_default"
        )
        is True
        and admission_decision.get("keep_queue_batch_default") is True,
        "default_runtime_change_blocked": admission_decision.get(
            "admit_default_runtime_behavior_change_now"
        )
        is False
        and impl_summary.get("runtime_default_change_allowed_now") is False,
        "s100p_runtime_blocked": admission_decision.get("admit_s100p_runtime_now")
        is False
        and impl_summary.get("s100p_runtime_experiment_allowed_now") is False,
        "compile_start_blocked": admission_decision.get("admit_compile_start_now")
        is False
        and impl_summary.get("compile_start_allowed_now") is False,
        "standard_sweeps_blocked": per_run_summary.get(
            "standard_b4_runtime_sweep_status"
        )
        == "blocked_duplicate",
        "final_logits_still_primary": per_run_summary.get("most_common_top_segment")
        == "seg27_final_logits"
        and float(per_run_summary.get("most_common_top_segment_rate") or 0.0) == 1.0,
        "no_runtime_or_compile_started": all(
            (report.get("audit") or {}).get(key) is False
            for report in [backlog, source_contract, impl_map, admission, per_run]
            for key in ["runtime_started", "compile_started"]
            if key in (report.get("audit") or {})
        ),
    }
    failed_checks = [key for key, value in checks.items() if not value]

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "tool_id": TOOL_ID,
        "verdict": "ok_dream7b_b4_runtime_refactor_work_order"
        if not failed_checks
        else "failed_dream7b_b4_runtime_refactor_work_order",
        "scope": "local source-anchored B=4 runtime refactor work order from existing telemetry only",
        "source_paths": {
            "runtime_source": str(args.source),
            "backlog": str(args.backlog_json),
            "source_contract": str(args.source_contract_json),
            "implementation_map": str(args.implementation_map_json),
            "admission_contract": str(args.admission_json),
            "per_run_matrix": str(args.per_run_matrix_json),
            "hidden_materialize_design_contract": str(
                args.hidden_materialize_design_json
            ),
            "hidden_materialize_telemetry_contract": str(
                args.hidden_materialize_telemetry_json
            ),
        },
        "summary": {
            "work_order_count": len(work_rows),
            "allowed_local_work_count": len(allowed_local_rows),
            "future_runtime_candidate_count": len(future_runtime_rows),
            "blocked_default_change_count": len(blocked_default_rows),
            "source_anchor_missing_count": sum(
                row["source_anchor_missing_count"] for row in work_rows
            ),
            "source_anchor_line_drift_count": sum(
                row["source_anchor_line_drift_count"] for row in work_rows
            ),
            "source_contract_missing_token_count": len(contract_missing_tokens),
            "primary_local_design_item": "alternative_hidden_materialize_avoidance",
            "primary_future_runtime_candidate": "final_logits_last_token_path",
            "primary_runtime_refactor_target": backlog_decision.get(
                "primary_runtime_refactor_target"
            ),
            "next_nonduplicate_runtime_candidate": per_run_summary.get(
                "next_nonduplicate_runtime_candidate"
            ),
            "most_common_top_segment": per_run_summary.get("most_common_top_segment"),
            "most_common_top_segment_rate": per_run_summary.get(
                "most_common_top_segment_rate"
            ),
            "standard_b4_runtime_sweep_status": per_run_summary.get(
                "standard_b4_runtime_sweep_status"
            ),
            "preferred_group_policy": per_run_summary.get("preferred_group_policy"),
            "preferred_inner_order": per_run_summary.get("preferred_inner_order"),
            "run_count": per_run_summary.get("run_count"),
            "successful_run_count": per_run_summary.get("successful_run_count"),
            "failed_run_count": per_run_summary.get("failed_run_count"),
            "segment_major_delta_vs_microbatch_major_ms_per_request": (
                (per_run_findings.get("inner_order_mb512") or {}).get(
                    "segment_major_ms_per_request_delta"
                )
            ),
            "hidden_materialize_design_contract_verdict": hidden_design.get(
                "verdict"
            ),
            "hidden_materialize_design_allowed_design_only_count": (
                hidden_design_summary.get("allowed_design_only_count")
            ),
            "hidden_materialize_design_source_anchor_missing_count": (
                hidden_design_summary.get("source_anchor_missing_count")
            ),
            "hidden_materialize_design_current_preallocate_hidden_rejected": (
                hidden_design_summary.get("current_preallocate_hidden_rejected")
            ),
            "hidden_materialize_design_next_design_only_item": (
                hidden_design_summary.get("next_design_only_item")
            ),
            "hidden_materialize_design_next_report_only_item": (
                hidden_design_summary.get("next_report_only_item")
            ),
            "hidden_materialize_design_default_runtime_change_allowed_now": (
                hidden_design_summary.get("default_runtime_change_allowed_now")
            ),
            "hidden_materialize_design_s100p_runtime_allowed_now": (
                hidden_design_summary.get("s100p_runtime_experiment_allowed_now")
            ),
            "hidden_materialize_design_compile_start_allowed_now": (
                hidden_design_summary.get("compile_start_allowed_now")
            ),
            "hidden_materialize_telemetry_contract_verdict": hidden_telemetry.get(
                "verdict"
            ),
            "hidden_materialize_telemetry_required_field_count": (
                hidden_telemetry_summary.get("required_telemetry_field_count")
            ),
            "hidden_materialize_telemetry_source_anchor_missing_count": (
                hidden_telemetry_summary.get("source_anchor_missing_count")
            ),
            "hidden_materialize_telemetry_source_ready": (
                hidden_telemetry_decision.get("telemetry_source_ready")
            ),
            "hidden_materialize_telemetry_default_runtime_change_allowed_now": (
                hidden_telemetry_summary.get("default_runtime_change_allowed_now")
            ),
            "hidden_materialize_telemetry_s100p_runtime_allowed_now": (
                hidden_telemetry_summary.get("s100p_runtime_experiment_allowed_now")
            ),
            "hidden_materialize_telemetry_compile_start_allowed_now": (
                hidden_telemetry_summary.get("compile_start_allowed_now")
            ),
            "best_nonbaseline_group_or_order_status": "slower_than_baseline",
            "queue_batch_remains_default": backlog_decision.get(
                "queue_batch_remains_default"
            )
            is True
            and admission_decision.get("keep_queue_batch_default") is True,
            "default_runtime_change_allowed_now": False,
            "s100p_runtime_experiment_allowed_now": False,
            "compile_start_allowed_now": False,
            "compile_preflight_only_allowed_now": admission_decision.get(
                "admit_compile_preflight_only_now"
            )
            is True,
            "runtime_started": False,
            "compile_started": False,
            "remote_access_performed": False,
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "work_order_rows": work_rows,
        "contract_source_tokens_missing": contract_missing_tokens,
        "decision": {
            "next_local_work": [
                row["id"] for row in allowed_local_rows
            ],
            "hidden_materialize_next_design_only_item": hidden_design_summary.get(
                "next_design_only_item"
            ),
            "hidden_materialize_next_report_only_item": hidden_design_summary.get(
                "next_report_only_item"
            ),
            "hidden_materialize_next_evidence_gate": hidden_telemetry_decision.get(
                "next_evidence_gate"
            ),
            "do_not_change_runtime_defaults_now": True,
            "do_not_start_s100p_runtime_now": True,
            "do_not_start_compile_now": True,
            "do_not_run_more_standard_b4_runtime_sweeps_now": True,
            "keep_queue_batch_default": True,
            "next_external_gate": "last-token HBM manifest verification before mb512 runtime validation",
        },
        "audit": {
            "source_modified": False,
            "runtime_started": False,
            "compile_started": False,
            "remote_access_performed": False,
            "service_restarted": False,
            "local_writes": "JSON/Markdown runtime refactor work order only",
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    decision = payload["decision"]
    lines = [
        "# Dream7B B=4 Runtime Refactor Work Order",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- work_order_count: `{summary['work_order_count']}`",
        f"- allowed_local_work_count: `{summary['allowed_local_work_count']}`",
        f"- future_runtime_candidate_count: `{summary['future_runtime_candidate_count']}`",
        f"- source_anchor_missing_count: `{summary['source_anchor_missing_count']}`",
        f"- source_contract_missing_token_count: `{summary['source_contract_missing_token_count']}`",
        f"- primary_local_design_item: `{summary['primary_local_design_item']}`",
        f"- primary_future_runtime_candidate: `{summary['primary_future_runtime_candidate']}`",
        f"- most_common_top_segment: `{summary['most_common_top_segment']}` @ `{summary['most_common_top_segment_rate']}`",
        f"- standard_b4_runtime_sweep_status: `{summary['standard_b4_runtime_sweep_status']}`",
        f"- preferred_group_policy: `{summary['preferred_group_policy']}`",
        f"- preferred_inner_order: `{summary['preferred_inner_order']}`",
        f"- hidden_materialize_design_contract_verdict: `{summary['hidden_materialize_design_contract_verdict']}`",
        f"- hidden_materialize_design_allowed_design_only_count: `{summary['hidden_materialize_design_allowed_design_only_count']}`",
        f"- hidden_materialize_design_source_anchor_missing_count: `{summary['hidden_materialize_design_source_anchor_missing_count']}`",
        f"- hidden_materialize_design_current_preallocate_hidden_rejected: `{summary['hidden_materialize_design_current_preallocate_hidden_rejected']}`",
        f"- hidden_materialize_design_next_design_only_item: `{summary['hidden_materialize_design_next_design_only_item']}`",
        f"- hidden_materialize_design_next_report_only_item: `{summary['hidden_materialize_design_next_report_only_item']}`",
        f"- hidden_materialize_design_default_runtime_change_allowed_now: `{summary['hidden_materialize_design_default_runtime_change_allowed_now']}`",
        f"- hidden_materialize_design_s100p_runtime_allowed_now: `{summary['hidden_materialize_design_s100p_runtime_allowed_now']}`",
        f"- hidden_materialize_design_compile_start_allowed_now: `{summary['hidden_materialize_design_compile_start_allowed_now']}`",
        f"- hidden_materialize_telemetry_contract_verdict: `{summary['hidden_materialize_telemetry_contract_verdict']}`",
        f"- hidden_materialize_telemetry_required_field_count: `{summary['hidden_materialize_telemetry_required_field_count']}`",
        f"- hidden_materialize_telemetry_source_anchor_missing_count: `{summary['hidden_materialize_telemetry_source_anchor_missing_count']}`",
        f"- hidden_materialize_telemetry_source_ready: `{summary['hidden_materialize_telemetry_source_ready']}`",
        f"- hidden_materialize_telemetry_default_runtime_change_allowed_now: `{summary['hidden_materialize_telemetry_default_runtime_change_allowed_now']}`",
        f"- hidden_materialize_telemetry_s100p_runtime_allowed_now: `{summary['hidden_materialize_telemetry_s100p_runtime_allowed_now']}`",
        f"- hidden_materialize_telemetry_compile_start_allowed_now: `{summary['hidden_materialize_telemetry_compile_start_allowed_now']}`",
        f"- queue_batch_remains_default: `{summary['queue_batch_remains_default']}`",
        f"- default_runtime_change_allowed_now: `{summary['default_runtime_change_allowed_now']}`",
        f"- s100p_runtime_experiment_allowed_now: `{summary['s100p_runtime_experiment_allowed_now']}`",
        f"- compile_start_allowed_now: `{summary['compile_start_allowed_now']}`",
        f"- compile_preflight_only_allowed_now: `{summary['compile_preflight_only_allowed_now']}`",
        f"- next_local_work: `{', '.join(decision['next_local_work'])}`",
        f"- next_external_gate: `{decision['next_external_gate']}`",
        "",
        "## Work Orders",
        "",
    ]
    for row in payload["work_order_rows"]:
        lines.extend(
            [
                f"### {row['rank']}. {row['id']}",
                "",
                f"- status: `{row['status']}`",
                f"- work_type: `{row['work_type']}`",
                f"- allowed_now: `{row['allowed_now']}`",
                f"- default_behavior_change_allowed_now: `{row['default_behavior_change_allowed_now']}`",
                f"- source_anchors_all_present: `{row['source_anchors_all_present']}`",
                f"- source_anchor_missing_count: `{row['source_anchor_missing_count']}`",
                f"- projected_saved_ms_per_request: `{row['projected_saved_ms_per_request']}`",
                f"- expected_ceiling_ms_per_request: `{row['expected_ceiling_ms_per_request']}`",
                f"- local_next_action: `{row['local_next_action']}`",
                "",
            ]
        )
        if row["id"] == "alternative_hidden_materialize_avoidance":
            lines.extend(
                [
                    f"- hidden_materialize_design_contract_verdict: `{row['hidden_materialize_design_contract_verdict']}`",
                    f"- hidden_materialize_design_allowed_design_only_count: `{row['hidden_materialize_design_allowed_design_only_count']}`",
                    f"- hidden_materialize_design_current_preallocate_hidden_rejected: `{row['hidden_materialize_design_current_preallocate_hidden_rejected']}`",
                    f"- hidden_materialize_design_next_design_only_item: `{row['hidden_materialize_design_next_design_only_item']}`",
                    f"- hidden_materialize_design_next_report_only_item: `{row['hidden_materialize_design_next_report_only_item']}`",
                    f"- hidden_materialize_telemetry_contract_verdict: `{row['hidden_materialize_telemetry_contract_verdict']}`",
                    f"- hidden_materialize_telemetry_required_field_count: `{row['hidden_materialize_telemetry_required_field_count']}`",
                    f"- hidden_materialize_telemetry_source_anchor_missing_count: `{row['hidden_materialize_telemetry_source_anchor_missing_count']}`",
                    f"- hidden_materialize_telemetry_source_ready: `{row['hidden_materialize_telemetry_source_ready']}`",
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
            f"- service_restarted: `{payload['audit']['service_restarted']}`",
            f"- failed_checks: `{payload['failed_checks']}`",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--backlog-json", type=Path, default=DEFAULT_BACKLOG)
    parser.add_argument("--source-contract-json", type=Path, default=DEFAULT_SOURCE_CONTRACT)
    parser.add_argument("--implementation-map-json", type=Path, default=DEFAULT_IMPL_MAP)
    parser.add_argument("--admission-json", type=Path, default=DEFAULT_ADMISSION)
    parser.add_argument("--per-run-matrix-json", type=Path, default=DEFAULT_PER_RUN)
    parser.add_argument(
        "--hidden-materialize-design-json", type=Path, default=DEFAULT_HIDDEN_DESIGN
    )
    parser.add_argument(
        "--hidden-materialize-telemetry-json",
        type=Path,
        default=DEFAULT_HIDDEN_TELEMETRY,
    )
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    args.out_md.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"verdict": payload["verdict"], "json": str(args.out_json), "md": str(args.out_md)}, indent=2))


if __name__ == "__main__":
    main()
