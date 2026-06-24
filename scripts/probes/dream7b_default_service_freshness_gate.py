#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def report_sort_key(path: Path) -> tuple[float, float, str]:
    payload = read_json(path) or {}
    parsed = parse_time(payload.get("generated_at"))
    generated_ts = parsed.timestamp() if parsed else 0.0
    try:
        mtime_ts = path.stat().st_mtime
    except OSError:
        mtime_ts = 0.0
    return generated_ts, mtime_ts, str(path)


def latest_report(root: Path, filename: str) -> dict[str, Any]:
    candidates = [path for path in root.rglob(filename) if path.is_file()] if root.exists() else []
    if not candidates:
        return {"found": False, "path": None, "payload": None}
    selected = max(candidates, key=report_sort_key)
    payload = read_json(selected)
    return {
        "found": payload is not None,
        "path": str(selected),
        "payload": payload,
        "generated_at": payload.get("generated_at") if payload else None,
        "verdict": payload.get("verdict") if payload else None,
    }


def age_minutes(value: str | None, now: datetime) -> float | None:
    parsed = parse_time(value)
    if parsed is None:
        return None
    return round((now - parsed).total_seconds() / 60.0, 3)


def run_cmd(args: list[str], timeout: int = 30) -> dict[str, Any]:
    completed = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    return {
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def ssh_cmd(args: argparse.Namespace, remote_command: str, timeout: int = 30) -> dict[str, Any]:
    return run_cmd(
        [
            "ssh.exe",
            "-i",
            str(args.ssh_key),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            args.remote_host,
            remote_command,
        ],
        timeout=timeout,
    )


def parse_kv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def remote_default_state(args: argparse.Namespace) -> dict[str, Any]:
    remote_script = "\n".join(
        [
            "set -u",
            "echo queue_pending_count=$(sudo -n find /mnt/nas/openclaw/queues/dream7b-bpu/pending -type f 2>/dev/null | wc -l)",
            "echo queue_processing_count=$(sudo -n find /mnt/nas/openclaw/queues/dream7b-bpu/processing -type f 2>/dev/null | wc -l)",
            "echo queue_active=$(systemctl is-active dream7b-bpu-batch-queue.service 2>/dev/null || true)",
            "echo queue_enabled=$(systemctl is-enabled dream7b-bpu-batch-queue.service 2>/dev/null || true)",
            "echo gateway_active=$(sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active dream7b-local-openai-gateway.service 2>/dev/null || true)",
            "echo gateway_enabled=$(sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-enabled dream7b-local-openai-gateway.service 2>/dev/null || true)",
            "echo gateway_main_pid=$(sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user show dream7b-local-openai-gateway.service -p MainPID --value 2>/dev/null || true)",
            "echo listener_pid=$(sudo -n lsof -t -iTCP:18888 -sTCP:LISTEN -P -n 2>/dev/null | head -1 || true)",
            "echo openclaw_gateway_active=$(sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active openclaw-gateway.service 2>/dev/null || true)",
            "echo health_json=$(curl -sS --max-time 3 http://127.0.0.1:18888/health 2>/dev/null | tr -d '\\n' || true)",
        ]
    )
    result = ssh_cmd(args, remote_script, timeout=args.remote_timeout_sec)
    values = parse_kv(result["stdout"])
    return {
        "returncode": result["returncode"],
        "stderr": result["stderr"],
        "queue_pending_count": int(values.get("queue_pending_count") or 0),
        "queue_processing_count": int(values.get("queue_processing_count") or 0),
        "queue_active": values.get("queue_active"),
        "queue_enabled": values.get("queue_enabled"),
        "gateway_active": values.get("gateway_active"),
        "gateway_enabled": values.get("gateway_enabled"),
        "gateway_main_pid": values.get("gateway_main_pid"),
        "listener_pid": values.get("listener_pid"),
        "openclaw_gateway_active": values.get("openclaw_gateway_active"),
        "health_json": values.get("health_json"),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    packet_report = latest_report(args.snapshot_root, "dream7b_product_decision_packet.json")
    packet = packet_report.get("payload") or {}
    service = packet.get("service") or {}
    decision = packet.get("decision") or {}
    evidence = packet.get("product_evidence") or {}
    first_response = packet.get("first_response") or {}
    first_response_slo_tier = packet.get("first_response_slo_tier_guard") or {}
    first_response_warning_triage = packet.get("first_response_warning_triage") or {}
    slo_limited_evidence_triage = packet.get("slo_limited_evidence_triage") or {}
    inventory = packet.get("true_batch_nas_inventory") or {}
    group_order = packet.get("group_order_candidates") or {}
    group_partition = packet.get("group_partition_planner") or {}
    group_inner_order_value = packet.get("group_inner_order_value_audit") or {}
    scheduler = packet.get("scheduler_overhead_budget") or {}
    group_switch = packet.get("group_switch_accounting") or {}
    segment_group_schedule = packet.get("segment_group_schedule_scorecard") or {}
    per_run_evidence_matrix = packet.get("per_run_evidence_matrix") or {}
    runtime_instrumentation = packet.get("runtime_instrumentation") or {}
    workstream_overlap = packet.get("workstream_overlap_audit") or {}
    tuning_matrix = packet.get("tuning_decision_matrix") or {}
    runtime_refactor_backlog = packet.get("runtime_refactor_backlog") or {}
    runtime_refactor_source_contract = packet.get("runtime_refactor_source_contract") or {}
    runtime_refactor_admission_contract = packet.get("runtime_refactor_admission_contract") or {}
    runtime_source_implementation_map = packet.get("runtime_source_implementation_map") or {}
    runtime_refactor_work_order = packet.get("runtime_refactor_work_order") or {}
    hidden_materialize_design_contract = (
        packet.get("hidden_materialize_design_contract") or {}
    )
    hidden_materialize_telemetry_contract = (
        packet.get("hidden_materialize_telemetry_contract") or {}
    )
    hbm_load_accounting_contract = packet.get("hbm_load_accounting_contract") or {}
    bottleneck_closure = packet.get("bottleneck_closure_model") or {}
    runtime_gate = packet.get("runtime_experiment_gate") or {}
    runtime_command_guard = packet.get("runtime_command_guard") or {}
    compile_command_guard = packet.get("compile_command_guard") or {}
    next_action_pack = packet.get("next_action_admission_pack") or {}
    final_logits_leverage = packet.get("final_logits_leverage_model") or {}
    packet_age = age_minutes(packet.get("generated_at"), now)
    queue_partial_batch_flush_ready = evidence.get("queue_partial_batch_flush_ready")
    if queue_partial_batch_flush_ready is None:
        queue_partial_batch_flush_ready = service.get("queue_partial_batch_flush_ready")
    queue_partial_batch_flush_live_summary_ready = evidence.get(
        "queue_partial_batch_flush_live_summary_ready"
    )
    if queue_partial_batch_flush_live_summary_ready is None:
        queue_partial_batch_flush_live_summary_ready = service.get(
            "queue_partial_batch_flush_live_summary_ready"
        )
    queue_partial_batch_flush_probe_ready = evidence.get(
        "queue_partial_batch_flush_probe_ready"
    )
    if queue_partial_batch_flush_probe_ready is None:
        queue_partial_batch_flush_probe_ready = service.get(
            "queue_partial_batch_flush_probe_ready"
        )
    queue_partial_batch_flush_health_snapshot_ready = evidence.get(
        "queue_partial_batch_flush_health_snapshot_ready"
    )
    if queue_partial_batch_flush_health_snapshot_ready is None:
        queue_partial_batch_flush_health_snapshot_ready = service.get(
            "queue_partial_batch_flush_health_snapshot_ready"
        )
    queue_partial_batch_flush_probe_or_health_ready = (
        queue_partial_batch_flush_probe_ready is True
        or queue_partial_batch_flush_health_snapshot_ready is True
    )
    queue_partial_batch_flush_readiness_source = evidence.get(
        "queue_partial_batch_flush_readiness_source"
    ) or service.get("queue_partial_batch_flush_readiness_source")
    queue_partial_batch_probe_run_dir = evidence.get(
        "queue_partial_batch_probe_run_dir"
    ) or service.get("queue_partial_batch_probe_run_dir")
    queue_partial_batch_probe_ms_per_request = evidence.get(
        "queue_partial_batch_probe_ms_per_request"
    )
    if queue_partial_batch_probe_ms_per_request is None:
        queue_partial_batch_probe_ms_per_request = service.get(
            "queue_partial_batch_probe_ms_per_request"
        )

    remote_state = remote_default_state(args)
    product_packet_guardrailed_warning = (
        packet.get("verdict") == "warning_dream7b_product_decision_packet"
        and decision.get("production_default") == "queue_batch"
        and decision.get("true_batch_b4_status") == "research_artifact_not_promoted"
        and decision.get("queue_should_remain_default") is True
        and runtime_refactor_admission_contract.get("queue_batch_remains_default")
        is True
        and runtime_refactor_admission_contract.get(
            "default_runtime_code_change_allowed_now"
        )
        is False
        and runtime_refactor_admission_contract.get("s100p_runtime_experiment_allowed_now")
        is False
        and runtime_refactor_admission_contract.get("compile_start_allowed_now")
        is False
        and runtime_refactor_admission_contract.get("compile_preflight_only_allowed_now")
        is True
        and runtime_refactor_admission_contract.get(
            "block_standard_group_or_inner_order_sweeps"
        )
        is True
        and runtime_refactor_admission_contract.get("block_prewarm_or_cache_default")
        is True
        and not (runtime_refactor_admission_contract.get("failed_checks") or [])
        and runtime_source_implementation_map.get("queue_batch_remains_default")
        is True
        and runtime_source_implementation_map.get("runtime_default_change_allowed_now")
        is False
        and runtime_source_implementation_map.get("s100p_runtime_experiment_allowed_now")
        is False
        and runtime_source_implementation_map.get("compile_start_allowed_now") is False
        and runtime_source_implementation_map.get(
            "standard_group_inner_order_sweeps_blocked"
        )
        is True
        and not (runtime_source_implementation_map.get("failed_checks") or [])
        and hidden_materialize_design_contract.get("verdict")
        == "ok_dream7b_b4_hidden_materialize_design_contract"
        and hidden_materialize_design_contract.get(
            "default_runtime_change_allowed_now"
        )
        is False
        and hidden_materialize_design_contract.get(
            "s100p_runtime_experiment_allowed_now"
        )
        is False
        and hidden_materialize_design_contract.get("compile_start_allowed_now")
        is False
        and not (hidden_materialize_design_contract.get("failed_checks") or [])
        and hidden_materialize_telemetry_contract.get("verdict")
        == "ok_dream7b_b4_hidden_materialize_telemetry_contract"
        and hidden_materialize_telemetry_contract.get(
            "default_runtime_change_allowed_now"
        )
        is False
        and hidden_materialize_telemetry_contract.get(
            "s100p_runtime_experiment_allowed_now"
        )
        is False
        and hidden_materialize_telemetry_contract.get("compile_start_allowed_now")
        is False
        and not (hidden_materialize_telemetry_contract.get("failed_checks") or [])
    )
    packet_verdict_accepted = (
        packet.get("verdict") == "ok_dream7b_product_decision_packet"
        or product_packet_guardrailed_warning
    )
    checks = {
        "packet_found": packet_report.get("found") is True,
        "packet_fresh": packet_age is not None and packet_age <= args.max_packet_age_minutes,
        "packet_verdict_accepted": packet_verdict_accepted,
        "production_default_queue_batch": decision.get("production_default") == "queue_batch",
        "true_batch_b4_not_promoted": decision.get("true_batch_b4_status")
        == "research_artifact_not_promoted",
        "queue_should_remain_default": decision.get("queue_should_remain_default") is True,
        "packet_service_active_enabled": service.get("active") is True and service.get("enabled") is True,
        "packet_gateway_active_enabled": service.get("gateway_active") is True
        and service.get("gateway_enabled") is True,
        "packet_queue_idle": str(packet.get("queue_pending_count")) == "0"
        and str(packet.get("queue_processing_count")) == "0",
        "queue_partial_batch_flush_ready": queue_partial_batch_flush_ready is True,
        "queue_partial_batch_flush_probe_or_health_ready": queue_partial_batch_flush_probe_or_health_ready,
        "queue_partial_batch_flush_live_summary_state_recorded": queue_partial_batch_flush_live_summary_ready
        in (True, False),
        "queue_partial_batch_flush_probe_ready": queue_partial_batch_flush_probe_ready
        is True,
        "queue_partial_batch_flush_health_snapshot_ready": queue_partial_batch_flush_health_snapshot_ready
        is True,
        "guardrail_ok": evidence.get("guardrail_verdict") == "ok_dream7b_product_guardrail_snapshot",
        "rollback_dry_run_ready": evidence.get("guardrail_default_rollback_dry_run_ready")
        is True,
        "slo_ok_no_blockers": evidence.get("slo_verdict")
        == "ok_ai_nas_operational_slo_rollup_contract"
        and int(evidence.get("slo_blocker_count") or 0) == 0,
        "portal_ok_report_only": evidence.get("portal_verdict")
        == "ok_ai_nas_operator_portal_contract"
        and evidence.get("portal_execution_performed") is False,
        "gateway_listener_owned": evidence.get("gateway_listener_matches_systemd_main_pid")
        is True
        and evidence.get("gateway_orphan_listener_detected") is False,
        "gateway_listener_drift_ok": evidence.get("gateway_listener_drift_gate_verdict")
        == "ok_dream7b_gateway_listener_drift_gate"
        and evidence.get("gateway_listener_drift_warning_count") == 0,
        "first_response_fast_status_ok": first_response.get("fast_status_verdict")
        == "ok_dream7b_first_response_fast_status_packet",
        "first_response_slo_tier_guard_ok": first_response_slo_tier.get("verdict")
        == "ok_dream7b_first_response_slo_tier_guard"
        and not (first_response_slo_tier.get("failed_checks") or [])
        and first_response_slo_tier.get("fast_paths_satisfy_interactive_first_content_slo")
        is True
        and first_response_slo_tier.get("sse_progress_satisfies_interactive_progress_slo")
        is True
        and first_response_slo_tier.get(
            "backend_first_content_latency_is_not_true_batch_work"
        )
        is True,
        "first_response_slo_starts_no_runtime_or_compile": first_response_slo_tier.get(
            "runtime_started"
        )
        is False
        and first_response_slo_tier.get("compile_started") is False,
        "first_response_warning_triage_ok": first_response_warning_triage.get(
            "verdict"
        )
        == "ok_dream7b_first_response_warning_triage"
        and not (first_response_warning_triage.get("failed_checks") or [])
        and first_response_warning_triage.get("warning_is_product_triaged") is True
        and first_response_warning_triage.get(
            "backend_first_content_latency_is_not_true_batch_work"
        )
        is True
        and first_response_warning_triage.get(
            "do_not_promote_true_batch_for_first_response"
        )
        is True,
        "first_response_warning_triage_starts_no_runtime_or_compile": first_response_warning_triage.get(
            "runtime_started"
        )
        is False
        and first_response_warning_triage.get("compile_started") is False,
        "slo_limited_evidence_triage_ok": slo_limited_evidence_triage.get("verdict")
        == "ok_ai_nas_slo_limited_evidence_triage"
        and not (slo_limited_evidence_triage.get("failed_checks") or [])
        and slo_limited_evidence_triage.get("limited_evidence_triaged") is True
        and slo_limited_evidence_triage.get("release_blocker") is False
        and slo_limited_evidence_triage.get("slo_warnings")
        == ["concurrency_stability:limited_production_evidence"],
        "slo_limited_evidence_triage_starts_no_runtime_or_compile": slo_limited_evidence_triage.get(
            "runtime_started"
        )
        is False
        and slo_limited_evidence_triage.get("compile_started") is False,
        "nas_inventory_prevents_duplicate_sweeps": inventory.get(
            "run_more_standard_b4_runtime_sweeps_now"
        )
        is False,
        "nas_inventory_b4_json_mirrored": inventory.get(
            "b4_remote_json_local_count_match"
        )
        is True
        and inventory.get("remote_b4_group_major_report_json_count")
        == inventory.get("local_b4_json_count"),
        "group_order_partition_prevents_duplicate_sweeps": group_order.get(
            "no_observed_variant_beats_baseline"
        )
        is True
        and group_order.get("more_mb512_group_boundary_sweeps_deprioritized") is True
        and group_partition.get("run_new_partition_now") is False,
        "group_inner_order_value_audit_blocks_duplicate_sweeps": group_inner_order_value.get(
            "verdict"
        )
        == "ok_dream7b_b4_group_inner_order_value_audit"
        and group_inner_order_value.get("run_more_group_size_or_inner_order_sweeps_now")
        is False
        and group_inner_order_value.get(
            "group_size_and_inner_order_are_current_primary_levers"
        )
        is False
        and group_inner_order_value.get("next_s100p_runtime_experiment_allowed_now")
        is False
        and group_inner_order_value.get("next_compile_allowed_now") is False,
        "segment_group_schedule_scorecard_ok": segment_group_schedule.get("verdict")
        == "ok_dream7b_b4_segment_group_schedule_scorecard"
        and segment_group_schedule.get("primary_schedule_bottleneck")
        == "seg27_28_final_logits"
        and segment_group_schedule.get("preferred_group_policy")
        == "keep_existing_5_group_segment_major_default"
        and segment_group_schedule.get("preferred_inner_order") == "segment-major"
        and not (segment_group_schedule.get("failed_checks") or []),
        "segment_group_schedule_blocks_runtime_compile_sweeps": segment_group_schedule.get(
            "run_more_standard_b4_group_or_inner_order_sweeps_now"
        )
        is False
        and segment_group_schedule.get("run_new_group_partition_now") is False
        and segment_group_schedule.get("run_s100p_runtime_now") is False
        and segment_group_schedule.get("start_compile_now") is False
        and segment_group_schedule.get("compile_preflight_only_now") is True
        and segment_group_schedule.get("runtime_started") is False
        and segment_group_schedule.get("compile_started") is False
        and segment_group_schedule.get("remote_access_performed") is False,
        "per_run_evidence_matrix_ok": per_run_evidence_matrix.get("verdict")
        == "ok_dream7b_b4_per_run_evidence_matrix"
        and int(per_run_evidence_matrix.get("run_count") or 0) >= 20
        and int(per_run_evidence_matrix.get("successful_run_count") or 0) >= 19
        and int(per_run_evidence_matrix.get("failed_run_count") or 0) >= 1
        and per_run_evidence_matrix.get("most_common_top_segment")
        == "seg27_final_logits"
        and float(per_run_evidence_matrix.get("most_common_top_segment_rate") or 0.0)
        == 1.0
        and not (per_run_evidence_matrix.get("failed_checks") or []),
        "per_run_evidence_matrix_blocks_standard_sweeps": per_run_evidence_matrix.get(
            "standard_b4_runtime_sweep_status"
        )
        == "blocked_duplicate"
        and per_run_evidence_matrix.get(
            "run_more_standard_group_or_inner_order_sweeps_now"
        )
        is False
        and per_run_evidence_matrix.get("would_start_runtime") is False
        and per_run_evidence_matrix.get("would_start_compile") is False,
        "scheduler_overhead_deprioritizes_python_gap_tuning": scheduler.get(
            "deprioritize_python_inter_segment_gap_tuning"
        )
        is True
        and scheduler.get("final_excess_exceeds_group_switch_gap_50x") is True
        and group_switch.get("group_release_and_unaccounted_gap_not_primary") is True,
        "runtime_instrumentation_ready": runtime_instrumentation.get("contract_verdict")
        == "ok_dream7b_true_batch_runtime_instrumentation_contract"
        and runtime_instrumentation.get("deployment_verdict")
        == "ok_dream7b_true_batch_runtime_instrumentation_deployment_contract"
        and runtime_instrumentation.get("default_cli_changed") is False
        and runtime_instrumentation.get("runtime_order_changed") is False
        and runtime_instrumentation.get("active_true_batch_python") == 0.0
        and runtime_instrumentation.get("active_compile_true_batch") == 0.0,
        "workstream_overlap_audit_ok": workstream_overlap.get("verdict")
        == "ok_dream7b_workstream_overlap_audit",
        "workstream_queue_work_not_duplicate_true_batch": workstream_overlap.get(
            "queue_batch_work_duplicates_prior_true_batch_rental"
        )
        is False,
        "workstream_standard_true_batch_runtime_blocked": workstream_overlap.get(
            "do_not_start_standard_true_batch_runtime_now"
        )
        is True,
        "tuning_decision_matrix_ok": tuning_matrix.get("verdict")
        == "ok_dream7b_b4_tuning_decision_matrix",
        "tuning_group_order_keeps_current_default": tuning_matrix.get("preferred_group_policy")
        == "keep_existing_5_group_segment_major_default"
        and tuning_matrix.get("preferred_inner_order") == "segment-major",
        "tuning_blocks_runtime_and_compile_now": tuning_matrix.get(
            "next_s100p_runtime_experiment_allowed"
        )
        is False
        and tuning_matrix.get("next_compile_allowed") is False,
        "tuning_matrix_uses_final_logits_leverage": tuning_matrix.get(
            "primary_code_target_projected_saved_ms_per_request"
        )
        == final_logits_leverage.get("projection_saved_ms_per_request")
        and tuning_matrix.get("primary_code_target_not_bpu_promotion_proof") is True
        and tuning_matrix.get(
            "standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage"
        )
        is True,
        "runtime_experiment_gate_admission_evidence_ready": runtime_gate.get(
            "admission_evidence_ready"
        )
        is True
        and runtime_gate.get("final_logits_leverage_gate_ready") is True
        and runtime_gate.get("runtime_refactor_gate_ready") is True
        and runtime_gate.get("tuning_matrix_gate_ready") is True
        and runtime_gate.get("per_run_matrix_gate_ready") is True,
        "runtime_experiment_gate_admission_blocks_standard_sweeps": runtime_gate.get(
            "admission_projected_saved_ms_per_request"
        )
        == final_logits_leverage.get("projection_saved_ms_per_request")
        and runtime_gate.get("admission_not_bpu_promotion_proof") is True
        and runtime_gate.get("admission_standard_sweeps_blocked") is True,
        "runtime_experiment_gate_uses_per_run_matrix": runtime_gate.get(
            "per_run_matrix_gate_ready"
        )
        is True
        and runtime_gate.get("per_run_matrix_top_segment") == "seg27_final_logits"
        and float(runtime_gate.get("per_run_matrix_top_segment_rate") or 0.0) == 1.0
        and runtime_gate.get("per_run_matrix_standard_sweep_status")
        == "blocked_duplicate",
        "runtime_command_guard_blocks_standard_sweeps": runtime_command_guard.get(
            "verdict"
        )
        == "ok_dream7b_b4_runtime_command_guard"
        and runtime_command_guard.get("command_guard_active") is True
        and runtime_command_guard.get("standard_sweep_commands_blocked") is True,
        "runtime_command_guard_starts_no_runtime": runtime_command_guard.get(
            "command_admitted"
        )
        is False
        and runtime_command_guard.get("would_start_runtime") is False,
        "compile_command_guard_blocks_b8_full_compile": compile_command_guard.get(
            "verdict"
        )
        == "ok_dream7b_b4_compile_command_guard"
        and compile_command_guard.get("compile_guard_active") is True
        and compile_command_guard.get("only_single_segment_last_token_compile_allowed")
        is True
        and compile_command_guard.get("b8_full_compile_blocked") is True,
        "compile_command_guard_starts_no_compile": compile_command_guard.get(
            "command_admitted"
        )
        is False
        and compile_command_guard.get("would_start_compile") is False,
        "next_action_admission_pack_ok": next_action_pack.get("verdict")
        == "ok_dream7b_b4_next_action_admission_pack"
        and next_action_pack.get("queue_batch_product_work_allowed_now") is True
        and next_action_pack.get("local_runtime_refactor_analysis_allowed_now") is True
        and next_action_pack.get("compile_preflight_only_allowed_now") is True
        and next_action_pack.get("per_run_matrix_gate_ready") is True,
        "next_action_pack_starts_no_runtime_or_compile": next_action_pack.get(
            "would_start_runtime"
        )
        is False
        and next_action_pack.get("would_start_compile") is False,
        "next_action_pack_uses_per_run_matrix": next_action_pack.get(
            "per_run_matrix_gate_ready"
        )
        is True
        and next_action_pack.get("per_run_matrix_top_segment") == "seg27_final_logits"
        and float(next_action_pack.get("per_run_matrix_top_segment_rate") or 0.0)
        == 1.0
        and next_action_pack.get("per_run_matrix_standard_sweep_status")
        == "blocked_duplicate",
        "final_logits_leverage_model_ok": final_logits_leverage.get("verdict")
        == "ok_dream7b_b4_final_logits_leverage_model",
        "final_logits_leverage_blocks_premature_promotion": final_logits_leverage.get(
            "projection_is_not_bpu_promotion_proof"
        )
        is True
        and final_logits_leverage.get("do_not_promote_without_runtime_result") is True,
        "final_logits_leverage_blocks_standard_sweeps": final_logits_leverage.get(
            "do_not_run_standard_group_or_inner_order_sweeps"
        )
        is True,
        "runtime_refactor_backlog_rank1_final_logits": runtime_refactor_backlog.get(
            "verdict"
        )
        == "ok_dream7b_b4_runtime_refactor_backlog"
        and runtime_refactor_backlog.get("primary_runtime_refactor_target")
        == "final_logits_last_token_path",
        "runtime_refactor_backlog_uses_leverage_model": runtime_refactor_backlog.get(
            "rank1_projected_saved_ms_per_request"
        )
        == final_logits_leverage.get("projection_saved_ms_per_request")
        and runtime_refactor_backlog.get("rank1_projection_is_not_bpu_promotion_proof")
        is True,
        "runtime_refactor_backlog_blocks_standard_sweeps": runtime_refactor_backlog.get(
            "rank1_blocks_standard_group_or_inner_order_sweeps"
        )
        is True
        and runtime_refactor_backlog.get("do_not_change_runtime_defaults_now") is True
        and runtime_refactor_backlog.get("do_not_start_s100p_runtime_now") is True,
        "runtime_refactor_source_contract_ok": runtime_refactor_source_contract.get(
            "verdict"
        )
        == "ok_dream7b_b4_runtime_refactor_source_contract"
        and runtime_refactor_source_contract.get("cli_defaults_preserved") is True
        and runtime_refactor_source_contract.get("last_token_path_supported") is True
        and runtime_refactor_source_contract.get("telemetry_contract_ready") is True
        and runtime_refactor_source_contract.get("protected_telemetry_fields_ready")
        is True
        and int(
            runtime_refactor_source_contract.get("protected_telemetry_field_count") or 0
        )
        >= 22
        and int(
            runtime_refactor_source_contract.get("protected_telemetry_missing_count") or 0
        )
        == 0,
        "runtime_refactor_source_contract_preserves_defaults": runtime_refactor_source_contract.get(
            "runtime_order_changed"
        )
        is False
        and runtime_refactor_source_contract.get("default_promotes_experimental_flags")
        is False,
        "runtime_refactor_admission_contract_ok": runtime_refactor_admission_contract.get(
            "verdict"
        )
        == "ok_dream7b_b4_runtime_refactor_admission_contract"
        and runtime_refactor_admission_contract.get("local_report_only_refactor_allowed_now")
        is True
        and runtime_refactor_admission_contract.get("default_runtime_code_change_allowed_now")
        is False
        and runtime_refactor_admission_contract.get("s100p_runtime_experiment_allowed_now")
        is False
        and runtime_refactor_admission_contract.get("compile_start_allowed_now") is False
        and runtime_refactor_admission_contract.get("compile_preflight_only_allowed_now")
        is True
        and runtime_refactor_admission_contract.get("queue_batch_remains_default") is True
        and not (runtime_refactor_admission_contract.get("failed_checks") or []),
        "runtime_refactor_admission_blocks_runtime_compile_defaults": runtime_refactor_admission_contract.get(
            "admit_default_runtime_behavior_change_now"
        )
        is False
        and runtime_refactor_admission_contract.get("admit_s100p_runtime_now") is False
        and runtime_refactor_admission_contract.get("admit_compile_start_now") is False
        and runtime_refactor_admission_contract.get(
            "block_standard_group_or_inner_order_sweeps"
        )
        is True
        and runtime_refactor_admission_contract.get("block_prewarm_or_cache_default")
        is True,
        "runtime_source_implementation_map_ok": runtime_source_implementation_map.get(
            "verdict"
        )
        == "ok_dream7b_b4_runtime_source_implementation_map"
        and runtime_source_implementation_map.get("queue_batch_remains_default")
        is True
        and runtime_source_implementation_map.get("primary_runtime_refactor_target")
        == "seg27_28_last_token_logits_or_output_avoidance"
        and runtime_source_implementation_map.get("primary_schedule_bottleneck")
        == "seg27_28_final_logits"
        and runtime_source_implementation_map.get("preferred_group_policy")
        == "keep_existing_5_group_segment_major_default"
        and runtime_source_implementation_map.get("preferred_inner_order")
        == "segment-major"
        and int(runtime_source_implementation_map.get("source_pattern_count") or 0)
        >= 40
        and int(
            runtime_source_implementation_map.get("missing_source_pattern_count") or 0
        )
        == 0
        and not (runtime_source_implementation_map.get("failed_checks") or []),
        "runtime_source_implementation_map_blocks_runtime_compile_defaults": runtime_source_implementation_map.get(
            "runtime_default_change_allowed_now"
        )
        is False
        and runtime_source_implementation_map.get("s100p_runtime_experiment_allowed_now")
        is False
        and runtime_source_implementation_map.get("compile_start_allowed_now")
        is False
        and runtime_source_implementation_map.get(
            "standard_group_inner_order_sweeps_blocked"
        )
        is True
        and runtime_source_implementation_map.get("runtime_compile_not_started")
        is True
        and runtime_source_implementation_map.get("remote_access_not_performed")
        is True,
        "runtime_refactor_work_order_ok": runtime_refactor_work_order.get("verdict")
        == "ok_dream7b_b4_runtime_refactor_work_order"
        and int(runtime_refactor_work_order.get("work_order_count") or 0) >= 5
        and int(runtime_refactor_work_order.get("allowed_local_work_count") or 0) >= 1
        and int(runtime_refactor_work_order.get("source_anchor_missing_count") or 0)
        == 0
        and int(
            runtime_refactor_work_order.get("source_contract_missing_token_count") or 0
        )
        == 0
        and runtime_refactor_work_order.get("queue_batch_remains_default") is True
        and runtime_refactor_work_order.get("most_common_top_segment")
        == "seg27_final_logits"
        and runtime_refactor_work_order.get("standard_b4_runtime_sweep_status")
        == "blocked_duplicate"
        and not (runtime_refactor_work_order.get("failed_checks") or []),
        "runtime_refactor_work_order_blocks_runtime_compile_defaults": runtime_refactor_work_order.get(
            "default_runtime_change_allowed_now"
        )
        is False
        and runtime_refactor_work_order.get("s100p_runtime_experiment_allowed_now")
        is False
        and runtime_refactor_work_order.get("compile_start_allowed_now") is False
        and runtime_refactor_work_order.get("do_not_change_runtime_defaults_now")
        is True
        and runtime_refactor_work_order.get("do_not_start_s100p_runtime_now") is True
        and runtime_refactor_work_order.get("do_not_start_compile_now") is True
        and runtime_refactor_work_order.get(
            "do_not_run_more_standard_b4_runtime_sweeps_now"
        )
        is True
        and runtime_refactor_work_order.get("runtime_started") is False
        and runtime_refactor_work_order.get("compile_started") is False
        and runtime_refactor_work_order.get("remote_access_performed") is False,
        "hidden_materialize_design_contract_ok": hidden_materialize_design_contract.get(
            "verdict"
        )
        == "ok_dream7b_b4_hidden_materialize_design_contract"
        and int(
            hidden_materialize_design_contract.get("source_anchor_missing_count") or 0
        )
        == 0
        and int(
            hidden_materialize_design_contract.get("allowed_design_only_count") or 0
        )
        >= 2
        and hidden_materialize_design_contract.get(
            "current_preallocate_hidden_rejected"
        )
        is True
        and hidden_materialize_design_contract.get(
            "preallocate_hidden_experimental_flag_only"
        )
        is True
        and hidden_materialize_design_contract.get(
            "primary_target_remains_final_logits"
        )
        is True
        and not (hidden_materialize_design_contract.get("failed_checks") or []),
        "hidden_materialize_design_contract_blocks_runtime_compile_defaults": hidden_materialize_design_contract.get(
            "default_runtime_change_allowed_now"
        )
        is False
        and hidden_materialize_design_contract.get(
            "s100p_runtime_experiment_allowed_now"
        )
        is False
        and hidden_materialize_design_contract.get("compile_start_allowed_now")
        is False
        and hidden_materialize_design_contract.get(
            "promote_current_preallocate_hidden"
        )
        is False
        and hidden_materialize_design_contract.get("change_runtime_defaults_now")
        is False
        and hidden_materialize_design_contract.get("start_s100p_runtime_now")
        is False
        and hidden_materialize_design_contract.get("start_compile_now") is False
        and hidden_materialize_design_contract.get("runtime_started") is False
        and hidden_materialize_design_contract.get("compile_started") is False
        and hidden_materialize_design_contract.get("remote_access_performed") is False,
        "hidden_materialize_telemetry_contract_ok": hidden_materialize_telemetry_contract.get(
            "verdict"
        )
        == "ok_dream7b_b4_hidden_materialize_telemetry_contract"
        and int(
            hidden_materialize_telemetry_contract.get("source_anchor_missing_count")
            or 0
        )
        == 0
        and int(
            hidden_materialize_telemetry_contract.get(
                "required_telemetry_field_count"
            )
            or 0
        )
        >= 7
        and hidden_materialize_telemetry_contract.get(
            "current_preallocate_hidden_rejected"
        )
        is True
        and hidden_materialize_telemetry_contract.get("telemetry_source_ready")
        is True
        and not (hidden_materialize_telemetry_contract.get("failed_checks") or []),
        "hidden_materialize_telemetry_contract_blocks_runtime_compile_defaults": hidden_materialize_telemetry_contract.get(
            "default_runtime_change_allowed_now"
        )
        is False
        and hidden_materialize_telemetry_contract.get(
            "s100p_runtime_experiment_allowed_now"
        )
        is False
        and hidden_materialize_telemetry_contract.get("compile_start_allowed_now")
        is False
        and hidden_materialize_telemetry_contract.get("deploy_or_run_now") is False
        and hidden_materialize_telemetry_contract.get("change_runtime_defaults_now")
        is False
        and hidden_materialize_telemetry_contract.get("start_s100p_runtime_now")
        is False
        and hidden_materialize_telemetry_contract.get("start_compile_now") is False
        and hidden_materialize_telemetry_contract.get("default_behavior_changed")
        is False
        and hidden_materialize_telemetry_contract.get("runtime_started") is False
        and hidden_materialize_telemetry_contract.get("compile_started") is False
        and hidden_materialize_telemetry_contract.get("remote_access_performed") is False,
        "hbm_load_accounting_contract_ok": hbm_load_accounting_contract.get("verdict")
        == "ok_dream7b_true_batch_hbm_load_accounting_contract"
        and hbm_load_accounting_contract.get("per_segment_load_accounting_ready")
        is True
        and hbm_load_accounting_contract.get("group_load_accounting_ready") is True
        and hbm_load_accounting_contract.get("prewarm_accounting_ready") is True
        and hbm_load_accounting_contract.get("timing_summary_accounts_load_and_prewarm")
        is True
        and hbm_load_accounting_contract.get("prewarm_hbm_default_changed") is False
        and hbm_load_accounting_contract.get("runtime_started") is False
        and hbm_load_accounting_contract.get("compile_started") is False,
        "bottleneck_closure_model_ok": bottleneck_closure.get("verdict")
        == "ok_dream7b_b4_bottleneck_closure_model"
        and bottleneck_closure.get("primary_next_code_target")
        == "seg27_28_last_token_logits"
        and bottleneck_closure.get("run_more_group_size_or_inner_order_sweeps_now")
        is False
        and bottleneck_closure.get("projection_is_not_bpu_promotion_proof") is True
        and bottleneck_closure.get("requires_real_runtime_result_before_promotion")
        is True,
        "remote_queue_active_enabled": remote_state.get("queue_active") == "active"
        and remote_state.get("queue_enabled") == "enabled",
        "remote_gateway_active_enabled": remote_state.get("gateway_active") == "active"
        and remote_state.get("gateway_enabled") == "enabled",
        "remote_openclaw_gateway_active": remote_state.get("openclaw_gateway_active") == "active",
        "remote_listener_matches_gateway_pid": bool(remote_state.get("listener_pid"))
        and remote_state.get("listener_pid") == remote_state.get("gateway_main_pid"),
        "remote_queue_idle": remote_state.get("queue_pending_count") == 0
        and remote_state.get("queue_processing_count") == 0,
        "remote_health_ok": '"ok": true' in (remote_state.get("health_json") or ""),
    }
    failed = [key for key, value in checks.items() if not value]
    queue_batch_service_remains_default = (
        checks["production_default_queue_batch"]
        and checks["true_batch_b4_not_promoted"]
        and checks["queue_should_remain_default"]
        and checks["runtime_refactor_admission_contract_ok"]
        and checks["runtime_refactor_admission_blocks_runtime_compile_defaults"]
        and checks["runtime_source_implementation_map_ok"]
        and checks["runtime_source_implementation_map_blocks_runtime_compile_defaults"]
        and checks["runtime_refactor_work_order_ok"]
        and checks["runtime_refactor_work_order_blocks_runtime_compile_defaults"]
        and checks["hidden_materialize_design_contract_ok"]
        and checks["hidden_materialize_design_contract_blocks_runtime_compile_defaults"]
        and checks["hidden_materialize_telemetry_contract_ok"]
        and checks["hidden_materialize_telemetry_contract_blocks_runtime_compile_defaults"]
        and checks["queue_partial_batch_flush_ready"]
        and checks["queue_partial_batch_flush_probe_or_health_ready"]
        and checks["segment_group_schedule_scorecard_ok"]
        and checks["segment_group_schedule_blocks_runtime_compile_sweeps"]
        and checks["per_run_evidence_matrix_ok"]
        and checks["per_run_evidence_matrix_blocks_standard_sweeps"]
        and checks["runtime_experiment_gate_uses_per_run_matrix"]
        and checks["next_action_pack_uses_per_run_matrix"]
        and checks["runtime_command_guard_starts_no_runtime"]
        and checks["compile_command_guard_starts_no_compile"]
        and checks["next_action_pack_starts_no_runtime_or_compile"]
        and checks["first_response_warning_triage_ok"]
        and checks["first_response_warning_triage_starts_no_runtime_or_compile"]
        and checks["slo_limited_evidence_triage_ok"]
        and checks["slo_limited_evidence_triage_starts_no_runtime_or_compile"]
    )
    verdict = "ok_dream7b_default_service_freshness_gate" if not failed else "warning_dream7b_default_service_freshness_gate"
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "source_paths": {
            "product_decision_packet": packet_report.get("path"),
        },
        "freshness": {
            "max_packet_age_minutes": args.max_packet_age_minutes,
            "packet_generated_at": packet.get("generated_at"),
            "packet_age_minutes": packet_age,
        },
        "checks": checks,
        "failed_checks": failed,
        "packet_summary": {
            "verdict": packet.get("verdict"),
            "packet_verdict_accepted": packet_verdict_accepted,
            "product_packet_guardrailed_warning": product_packet_guardrailed_warning,
            "production_default": decision.get("production_default"),
            "true_batch_b4_status": decision.get("true_batch_b4_status"),
            "next_runtime_candidate": decision.get("next_runtime_candidate"),
            "queue_partial_batch_flush_ready": queue_partial_batch_flush_ready,
            "queue_partial_batch_flush_live_summary_ready": queue_partial_batch_flush_live_summary_ready,
            "queue_partial_batch_flush_probe_ready": queue_partial_batch_flush_probe_ready,
            "queue_partial_batch_flush_health_snapshot_ready": queue_partial_batch_flush_health_snapshot_ready,
            "queue_partial_batch_flush_readiness_source": queue_partial_batch_flush_readiness_source,
            "queue_partial_batch_probe_run_dir": queue_partial_batch_probe_run_dir,
            "queue_partial_batch_probe_ms_per_request": queue_partial_batch_probe_ms_per_request,
            "slo_verdict": evidence.get("slo_verdict"),
            "slo_blocker_count": evidence.get("slo_blocker_count"),
            "portal_verdict": evidence.get("portal_verdict"),
            "guardrail_verdict": evidence.get("guardrail_verdict"),
            "first_response_fast_status_verdict": first_response.get("fast_status_verdict"),
            "first_response_slo_tier_guard_verdict": first_response_slo_tier.get(
                "verdict"
            ),
            "first_response_slo_fast_path_max_first_content_ms": first_response_slo_tier.get(
                "fast_path_max_first_content_ms"
            ),
            "first_response_slo_sse_first_progress_p50_ms": first_response_slo_tier.get(
                "sse_first_progress_p50_ms"
            ),
            "first_response_slo_backend_explicit_first_content_p50_ms": first_response_slo_tier.get(
                "explicit_first_content_p50_ms"
            ),
            "first_response_backend_not_true_batch_work": first_response_slo_tier.get(
                "backend_first_content_latency_is_not_true_batch_work"
            ),
            "first_response_warning_triage_verdict": first_response_warning_triage.get(
                "verdict"
            ),
            "first_response_warning_triaged": first_response_warning_triage.get(
                "warning_is_product_triaged"
            ),
            "first_response_warning_source_verdict": first_response_warning_triage.get(
                "source_warning_verdict"
            ),
            "first_response_warning_quickpath_delta_ms": first_response_warning_triage.get(
                "quickpath_delta_ms"
            ),
            "first_response_warning_backend_not_true_batch_work": first_response_warning_triage.get(
                "backend_first_content_latency_is_not_true_batch_work"
            ),
            "slo_limited_evidence_triage_verdict": slo_limited_evidence_triage.get(
                "verdict"
            ),
            "slo_limited_evidence_triaged": slo_limited_evidence_triage.get(
                "limited_evidence_triaged"
            ),
            "slo_limited_evidence_release_blocker": slo_limited_evidence_triage.get(
                "release_blocker"
            ),
            "slo_limited_evidence_warnings": slo_limited_evidence_triage.get(
                "slo_warnings"
            ),
            "slo_limited_concurrency_verdict": slo_limited_evidence_triage.get(
                "concurrency_verdict"
            ),
            "slo_limited_dialog_health_error_count": slo_limited_evidence_triage.get(
                "dialog_health_error_count"
            ),
            "run_more_standard_b4_runtime_sweeps_now": inventory.get(
                "run_more_standard_b4_runtime_sweeps_now"
            ),
            "nas_remote_group_major_report_json_count": inventory.get(
                "remote_group_major_report_json_count"
            ),
            "nas_remote_b4_group_major_report_json_count": inventory.get(
                "remote_b4_group_major_report_json_count"
            ),
            "nas_local_b4_json_count": inventory.get("local_b4_json_count"),
            "nas_b4_remote_json_local_count_match": inventory.get(
                "b4_remote_json_local_count_match"
            ),
            "nas_missing_report_json_dirs": inventory.get("missing_report_json_dirs") or [],
            "group_order_no_observed_variant_beats_baseline": group_order.get(
                "no_observed_variant_beats_baseline"
            ),
            "group_order_best_nonbaseline_delta_ms_per_request": group_order.get(
                "best_nonbaseline_observed_variant_delta_ms_per_request"
            ),
            "group_partition_run_new_partition_now": group_partition.get(
                "run_new_partition_now"
            ),
            "group_inner_order_value_audit_verdict": group_inner_order_value.get(
                "verdict"
            ),
            "group_inner_order_best_nonbaseline_delta_ms_per_request": group_inner_order_value.get(
                "best_nonbaseline_delta_ms_per_request"
            ),
            "group_inner_order_run_more_sweeps_now": group_inner_order_value.get(
                "run_more_group_size_or_inner_order_sweeps_now"
            ),
            "group_inner_order_primary_lever": group_inner_order_value.get(
                "top_value_lever"
            ),
            "group_inner_order_capacity_probe_only_candidate_count": group_inner_order_value.get(
                "capacity_probe_only_candidate_count"
            ),
            "segment_group_schedule_scorecard_verdict": segment_group_schedule.get(
                "verdict"
            ),
            "segment_group_primary_schedule_bottleneck": segment_group_schedule.get(
                "primary_schedule_bottleneck"
            ),
            "segment_group_primary_code_target": segment_group_schedule.get(
                "primary_code_target"
            ),
            "segment_group_preferred_group_policy": segment_group_schedule.get(
                "preferred_group_policy"
            ),
            "segment_group_preferred_inner_order": segment_group_schedule.get(
                "preferred_inner_order"
            ),
            "segment_group_run_more_standard_sweeps_now": segment_group_schedule.get(
                "run_more_standard_b4_group_or_inner_order_sweeps_now"
            ),
            "segment_group_run_s100p_runtime_now": segment_group_schedule.get(
                "run_s100p_runtime_now"
            ),
            "segment_group_start_compile_now": segment_group_schedule.get(
                "start_compile_now"
            ),
            "segment_group_compile_preflight_only_now": segment_group_schedule.get(
                "compile_preflight_only_now"
            ),
            "segment_group_final_logits_compute_excess_ms_per_request": segment_group_schedule.get(
                "final_logits_compute_excess_ms_per_request"
            ),
            "segment_group_final_excess_to_group_switch_gap_ratio": segment_group_schedule.get(
                "final_excess_to_group_switch_gap_ratio"
            ),
            "segment_group_best_nonbaseline_group_delta_ms_per_request": segment_group_schedule.get(
                "best_nonbaseline_group_delta_ms_per_request"
            ),
            "per_run_evidence_matrix_verdict": per_run_evidence_matrix.get("verdict"),
            "per_run_evidence_matrix_run_count": per_run_evidence_matrix.get("run_count"),
            "per_run_evidence_matrix_successful_run_count": per_run_evidence_matrix.get(
                "successful_run_count"
            ),
            "per_run_evidence_matrix_failed_run_count": per_run_evidence_matrix.get(
                "failed_run_count"
            ),
            "per_run_evidence_matrix_top_segment": per_run_evidence_matrix.get(
                "most_common_top_segment"
            ),
            "per_run_evidence_matrix_top_segment_rate": per_run_evidence_matrix.get(
                "most_common_top_segment_rate"
            ),
            "per_run_evidence_matrix_standard_sweep_status": per_run_evidence_matrix.get(
                "standard_b4_runtime_sweep_status"
            ),
            "per_run_evidence_matrix_run_more_standard_group_or_inner_order_sweeps_now": per_run_evidence_matrix.get(
                "run_more_standard_group_or_inner_order_sweeps_now"
            ),
            "per_run_evidence_matrix_next_nonduplicate_runtime_candidate": per_run_evidence_matrix.get(
                "next_nonduplicate_runtime_candidate"
            ),
            "scheduler_primary_code_target": scheduler.get("primary_code_target"),
            "scheduler_deprioritize_python_inter_segment_gap_tuning": scheduler.get(
                "deprioritize_python_inter_segment_gap_tuning"
            ),
            "group_switch_gap_ms_per_request": group_switch.get(
                "group_switch_gap_ms_per_request"
            ),
            "final_excess_to_switch_gap_ratio": group_switch.get(
                "final_excess_to_switch_gap_ratio"
            ),
            "runtime_instrumentation_contract_verdict": runtime_instrumentation.get(
                "contract_verdict"
            ),
            "runtime_instrumentation_deployment_verdict": runtime_instrumentation.get(
                "deployment_verdict"
            ),
            "runtime_instrumentation_remote_probe_sha256": runtime_instrumentation.get(
                "remote_probe_sha256"
            ),
            "runtime_instrumentation_active_true_batch_python": runtime_instrumentation.get(
                "active_true_batch_python"
            ),
            "runtime_instrumentation_active_compile_true_batch": runtime_instrumentation.get(
                "active_compile_true_batch"
            ),
            "workstream_overlap_verdict": workstream_overlap.get("verdict"),
            "workstream_current_workstream": workstream_overlap.get("current_workstream"),
            "workstream_queue_work_duplicates_prior_true_batch_rental": workstream_overlap.get(
                "queue_batch_work_duplicates_prior_true_batch_rental"
            ),
            "workstream_remote_b4_group_major_report_count": workstream_overlap.get(
                "remote_b4_group_major_report_count"
            ),
            "workstream_remote_b4_group_major_report_json_count": workstream_overlap.get(
                "remote_b4_group_major_report_json_count"
            ),
            "workstream_local_b4_json_count": workstream_overlap.get("local_b4_json_count"),
            "workstream_b4_remote_json_local_count_match": workstream_overlap.get(
                "b4_remote_json_local_count_match"
            ),
            "tuning_decision_matrix_verdict": tuning_matrix.get("verdict"),
            "tuning_preferred_group_policy": tuning_matrix.get("preferred_group_policy"),
            "tuning_preferred_inner_order": tuning_matrix.get("preferred_inner_order"),
            "tuning_primary_code_target": tuning_matrix.get("primary_code_target"),
            "tuning_primary_code_target_projected_saved_ms_per_request": tuning_matrix.get(
                "primary_code_target_projected_saved_ms_per_request"
            ),
            "tuning_primary_code_target_not_bpu_promotion_proof": tuning_matrix.get(
                "primary_code_target_not_bpu_promotion_proof"
            ),
            "tuning_standard_sweeps_blocked_by_final_logits_leverage": tuning_matrix.get(
                "standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage"
            ),
            "runtime_gate_admission_evidence_ready": runtime_gate.get(
                "admission_evidence_ready"
            ),
            "runtime_gate_final_logits_leverage_gate_ready": runtime_gate.get(
                "final_logits_leverage_gate_ready"
            ),
            "runtime_gate_runtime_refactor_gate_ready": runtime_gate.get(
                "runtime_refactor_gate_ready"
            ),
            "runtime_gate_tuning_matrix_gate_ready": runtime_gate.get(
                "tuning_matrix_gate_ready"
            ),
            "runtime_gate_per_run_matrix_gate_ready": runtime_gate.get(
                "per_run_matrix_gate_ready"
            ),
            "runtime_gate_per_run_matrix_top_segment": runtime_gate.get(
                "per_run_matrix_top_segment"
            ),
            "runtime_gate_per_run_matrix_standard_sweep_status": runtime_gate.get(
                "per_run_matrix_standard_sweep_status"
            ),
            "runtime_gate_admission_projected_saved_ms_per_request": runtime_gate.get(
                "admission_projected_saved_ms_per_request"
            ),
            "runtime_gate_admission_standard_sweeps_blocked": runtime_gate.get(
                "admission_standard_sweeps_blocked"
            ),
            "runtime_command_guard_verdict": runtime_command_guard.get("verdict"),
            "runtime_command_guard_active": runtime_command_guard.get(
                "command_guard_active"
            ),
            "runtime_command_guard_standard_sweeps_blocked": runtime_command_guard.get(
                "standard_sweep_commands_blocked"
            ),
            "runtime_command_guard_command_admitted": runtime_command_guard.get(
                "command_admitted"
            ),
            "runtime_command_guard_would_start_runtime": runtime_command_guard.get(
                "would_start_runtime"
            ),
            "compile_command_guard_verdict": compile_command_guard.get("verdict"),
            "compile_command_guard_active": compile_command_guard.get(
                "compile_guard_active"
            ),
            "compile_command_guard_only_single_segment_last_token_compile_allowed": compile_command_guard.get(
                "only_single_segment_last_token_compile_allowed"
            ),
            "compile_command_guard_b8_full_compile_blocked": compile_command_guard.get(
                "b8_full_compile_blocked"
            ),
            "compile_command_guard_command_admitted": compile_command_guard.get(
                "command_admitted"
            ),
            "compile_command_guard_would_start_compile": compile_command_guard.get(
                "would_start_compile"
            ),
            "compile_command_guard_blocked_now_by_readiness": compile_command_guard.get(
                "blocked_now_by_readiness"
            ),
            "compile_command_guard_blocked_now_by_capacity": compile_command_guard.get(
                "blocked_now_by_capacity"
            ),
            "next_action_pack_verdict": next_action_pack.get("verdict"),
            "next_action_pack_allowed_now_count": next_action_pack.get("allowed_now_count"),
            "next_action_pack_preflight_only_count": next_action_pack.get(
                "preflight_only_count"
            ),
            "next_action_pack_blocked_action_count": next_action_pack.get(
                "blocked_action_count"
            ),
            "next_action_pack_would_start_runtime": next_action_pack.get(
                "would_start_runtime"
            ),
            "next_action_pack_would_start_compile": next_action_pack.get(
                "would_start_compile"
            ),
            "next_action_pack_per_run_matrix_gate_ready": next_action_pack.get(
                "per_run_matrix_gate_ready"
            ),
            "next_action_pack_per_run_matrix_top_segment": next_action_pack.get(
                "per_run_matrix_top_segment"
            ),
            "next_action_pack_per_run_matrix_standard_sweep_status": next_action_pack.get(
                "per_run_matrix_standard_sweep_status"
            ),
            "next_action_pack_only_future_runtime_candidate": next_action_pack.get(
                "only_future_runtime_candidate"
            ),
            "runtime_refactor_verdict": runtime_refactor_backlog.get("verdict"),
            "runtime_refactor_primary_target": runtime_refactor_backlog.get(
                "primary_runtime_refactor_target"
            ),
            "runtime_refactor_rank1_projected_saved_ms_per_request": runtime_refactor_backlog.get(
                "rank1_projected_saved_ms_per_request"
            ),
            "runtime_refactor_rank1_not_bpu_promotion_proof": runtime_refactor_backlog.get(
                "rank1_projection_is_not_bpu_promotion_proof"
            ),
            "runtime_refactor_rank1_blocks_standard_sweeps": runtime_refactor_backlog.get(
                "rank1_blocks_standard_group_or_inner_order_sweeps"
            ),
            "runtime_refactor_source_contract_verdict": runtime_refactor_source_contract.get(
                "verdict"
            ),
            "runtime_refactor_source_cli_defaults_preserved": runtime_refactor_source_contract.get(
                "cli_defaults_preserved"
            ),
            "runtime_refactor_source_last_token_path_supported": runtime_refactor_source_contract.get(
                "last_token_path_supported"
            ),
            "runtime_refactor_source_telemetry_contract_ready": runtime_refactor_source_contract.get(
                "telemetry_contract_ready"
            ),
            "runtime_refactor_source_protected_telemetry_field_count": runtime_refactor_source_contract.get(
                "protected_telemetry_field_count"
            ),
            "runtime_refactor_source_protected_telemetry_missing_count": runtime_refactor_source_contract.get(
                "protected_telemetry_missing_count"
            ),
            "runtime_refactor_source_runtime_order_changed": runtime_refactor_source_contract.get(
                "runtime_order_changed"
            ),
            "runtime_refactor_source_default_promotes_experimental_flags": runtime_refactor_source_contract.get(
                "default_promotes_experimental_flags"
            ),
            "runtime_source_implementation_map_verdict": runtime_source_implementation_map.get(
                "verdict"
            ),
            "runtime_source_implementation_area_count": runtime_source_implementation_map.get(
                "implementation_area_count"
            ),
            "runtime_source_pattern_count": runtime_source_implementation_map.get(
                "source_pattern_count"
            ),
            "runtime_source_missing_source_pattern_count": runtime_source_implementation_map.get(
                "missing_source_pattern_count"
            ),
            "runtime_source_primary_runtime_refactor_target": runtime_source_implementation_map.get(
                "primary_runtime_refactor_target"
            ),
            "runtime_source_primary_schedule_bottleneck": runtime_source_implementation_map.get(
                "primary_schedule_bottleneck"
            ),
            "runtime_source_allowed_now": runtime_source_implementation_map.get(
                "allowed_now"
            )
            or [],
            "runtime_source_duplicate_or_blocked_area_count": runtime_source_implementation_map.get(
                "duplicate_or_blocked_area_count"
            ),
            "runtime_source_s100p_runtime_allowed_now": runtime_source_implementation_map.get(
                "s100p_runtime_experiment_allowed_now"
            ),
            "runtime_source_compile_start_allowed_now": runtime_source_implementation_map.get(
                "compile_start_allowed_now"
            ),
            "runtime_source_runtime_default_change_allowed_now": runtime_source_implementation_map.get(
                "runtime_default_change_allowed_now"
            ),
            "runtime_source_standard_sweeps_blocked": runtime_source_implementation_map.get(
                "standard_group_inner_order_sweeps_blocked"
            ),
            "runtime_source_runtime_compile_not_started": runtime_source_implementation_map.get(
                "runtime_compile_not_started"
            ),
            "runtime_source_remote_access_not_performed": runtime_source_implementation_map.get(
                "remote_access_not_performed"
            ),
            "runtime_source_failed_checks": runtime_source_implementation_map.get(
                "failed_checks"
            )
            or [],
            "runtime_refactor_work_order_verdict": runtime_refactor_work_order.get(
                "verdict"
            ),
            "runtime_refactor_work_order_count": runtime_refactor_work_order.get(
                "work_order_count"
            ),
            "runtime_refactor_work_order_allowed_local_work_count": runtime_refactor_work_order.get(
                "allowed_local_work_count"
            ),
            "runtime_refactor_work_order_source_anchor_missing_count": runtime_refactor_work_order.get(
                "source_anchor_missing_count"
            ),
            "runtime_refactor_work_order_primary_local_design_item": runtime_refactor_work_order.get(
                "primary_local_design_item"
            ),
            "runtime_refactor_work_order_primary_future_runtime_candidate": runtime_refactor_work_order.get(
                "primary_future_runtime_candidate"
            ),
            "runtime_refactor_work_order_next_local_work": runtime_refactor_work_order.get(
                "next_local_work"
            )
            or [],
            "runtime_refactor_work_order_default_runtime_change_allowed_now": runtime_refactor_work_order.get(
                "default_runtime_change_allowed_now"
            ),
            "runtime_refactor_work_order_s100p_runtime_allowed_now": runtime_refactor_work_order.get(
                "s100p_runtime_experiment_allowed_now"
            ),
            "runtime_refactor_work_order_compile_start_allowed_now": runtime_refactor_work_order.get(
                "compile_start_allowed_now"
            ),
            "runtime_refactor_work_order_failed_checks": runtime_refactor_work_order.get(
                "failed_checks"
            )
            or [],
            "hidden_materialize_design_contract_verdict": hidden_materialize_design_contract.get(
                "verdict"
            ),
            "hidden_materialize_design_allowed_design_only_count": hidden_materialize_design_contract.get(
                "allowed_design_only_count"
            ),
            "hidden_materialize_design_source_anchor_missing_count": hidden_materialize_design_contract.get(
                "source_anchor_missing_count"
            ),
            "hidden_materialize_design_current_preallocate_hidden_rejected": hidden_materialize_design_contract.get(
                "current_preallocate_hidden_rejected"
            ),
            "hidden_materialize_design_next_design_only_item": hidden_materialize_design_contract.get(
                "next_design_only_item"
            ),
            "hidden_materialize_design_next_report_only_item": hidden_materialize_design_contract.get(
                "next_report_only_item"
            ),
            "hidden_materialize_design_default_runtime_change_allowed_now": hidden_materialize_design_contract.get(
                "default_runtime_change_allowed_now"
            ),
            "hidden_materialize_design_s100p_runtime_allowed_now": hidden_materialize_design_contract.get(
                "s100p_runtime_experiment_allowed_now"
            ),
            "hidden_materialize_design_compile_start_allowed_now": hidden_materialize_design_contract.get(
                "compile_start_allowed_now"
            ),
            "hidden_materialize_telemetry_contract_verdict": hidden_materialize_telemetry_contract.get(
                "verdict"
            ),
            "hidden_materialize_telemetry_required_field_count": hidden_materialize_telemetry_contract.get(
                "required_telemetry_field_count"
            ),
            "hidden_materialize_telemetry_source_anchor_missing_count": hidden_materialize_telemetry_contract.get(
                "source_anchor_missing_count"
            ),
            "hidden_materialize_telemetry_source_ready": hidden_materialize_telemetry_contract.get(
                "telemetry_source_ready"
            ),
            "hidden_materialize_telemetry_default_runtime_change_allowed_now": hidden_materialize_telemetry_contract.get(
                "default_runtime_change_allowed_now"
            ),
            "hidden_materialize_telemetry_s100p_runtime_allowed_now": hidden_materialize_telemetry_contract.get(
                "s100p_runtime_experiment_allowed_now"
            ),
            "hidden_materialize_telemetry_compile_start_allowed_now": hidden_materialize_telemetry_contract.get(
                "compile_start_allowed_now"
            ),
            "runtime_refactor_admission_contract_verdict": runtime_refactor_admission_contract.get(
                "verdict"
            ),
            "runtime_refactor_admission_local_report_only_allowed_now": runtime_refactor_admission_contract.get(
                "local_report_only_refactor_allowed_now"
            ),
            "runtime_refactor_admission_default_runtime_change_allowed_now": runtime_refactor_admission_contract.get(
                "default_runtime_code_change_allowed_now"
            ),
            "runtime_refactor_admission_s100p_runtime_allowed_now": runtime_refactor_admission_contract.get(
                "s100p_runtime_experiment_allowed_now"
            ),
            "runtime_refactor_admission_compile_start_allowed_now": runtime_refactor_admission_contract.get(
                "compile_start_allowed_now"
            ),
            "runtime_refactor_admission_compile_preflight_only_allowed_now": runtime_refactor_admission_contract.get(
                "compile_preflight_only_allowed_now"
            ),
            "runtime_refactor_admission_block_standard_sweeps": runtime_refactor_admission_contract.get(
                "block_standard_group_or_inner_order_sweeps"
            ),
            "runtime_refactor_admission_block_prewarm_or_cache_default": runtime_refactor_admission_contract.get(
                "block_prewarm_or_cache_default"
            ),
            "runtime_refactor_admission_failed_checks": runtime_refactor_admission_contract.get(
                "failed_checks"
            )
            or [],
            "hbm_load_accounting_contract_verdict": hbm_load_accounting_contract.get(
                "verdict"
            ),
            "hbm_per_segment_load_accounting_ready": hbm_load_accounting_contract.get(
                "per_segment_load_accounting_ready"
            ),
            "hbm_group_load_accounting_ready": hbm_load_accounting_contract.get(
                "group_load_accounting_ready"
            ),
            "hbm_prewarm_accounting_ready": hbm_load_accounting_contract.get(
                "prewarm_accounting_ready"
            ),
            "hbm_timing_summary_accounts_load_and_prewarm": hbm_load_accounting_contract.get(
                "timing_summary_accounts_load_and_prewarm"
            ),
            "hbm_prewarm_hbm_default_changed": hbm_load_accounting_contract.get(
                "prewarm_hbm_default_changed"
            ),
            "hbm_accounting_runtime_started": hbm_load_accounting_contract.get(
                "runtime_started"
            ),
            "hbm_accounting_compile_started": hbm_load_accounting_contract.get(
                "compile_started"
            ),
            "bottleneck_closure_model_verdict": bottleneck_closure.get("verdict"),
            "bottleneck_closure_latest_avg_bpu_gap_to_queue_points": bottleneck_closure.get(
                "latest_avg_bpu_gap_to_queue_points"
            ),
            "bottleneck_closure_primary_next_code_target": bottleneck_closure.get(
                "primary_next_code_target"
            ),
            "bottleneck_closure_final_logits_projection_saved_ms_per_request": bottleneck_closure.get(
                "final_logits_projection_saved_ms_per_request"
            ),
            "bottleneck_closure_hbm_group_load_ms_per_request": bottleneck_closure.get(
                "hbm_group_load_ms_per_request"
            ),
            "bottleneck_closure_release_plus_unaccounted_group_gap_ms_per_request": bottleneck_closure.get(
                "release_plus_unaccounted_group_gap_ms_per_request"
            ),
            "bottleneck_closure_projection_is_not_bpu_promotion_proof": bottleneck_closure.get(
                "projection_is_not_bpu_promotion_proof"
            ),
            "final_logits_leverage_verdict": final_logits_leverage.get("verdict"),
            "final_logits_leverage_projection_saved_ms_per_request": final_logits_leverage.get(
                "projection_saved_ms_per_request"
            ),
            "final_logits_leverage_projection_capture_pct": final_logits_leverage.get(
                "projection_capture_of_final_excess_pct"
            ),
            "final_logits_leverage_latest_projected_latency_reduction_pct": final_logits_leverage.get(
                "latest_projected_latency_reduction_pct"
            ),
            "final_logits_leverage_latest_nonzero_shortfall_points": final_logits_leverage.get(
                "latest_nonzero_shortfall_points"
            ),
            "final_logits_leverage_low_load_nonzero_shortfall_points": final_logits_leverage.get(
                "low_load_nonzero_shortfall_points"
            ),
            "final_logits_leverage_not_bpu_promotion_proof": final_logits_leverage.get(
                "projection_is_not_bpu_promotion_proof"
            ),
        },
        "remote_state": remote_state,
        "decision": {
            "queue_batch_service_remains_default": queue_batch_service_remains_default,
            "true_batch_b4_status": decision.get("true_batch_b4_status"),
            "do_not_promote_true_batch": True,
            "rerun_product_packet_if_stale": checks["packet_fresh"] is False,
        },
    }


def render_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dream7B Default Service Freshness Gate",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- failed_checks: `{payload['failed_checks']}`",
        f"- packet_age_minutes: `{payload['freshness']['packet_age_minutes']}`",
        f"- max_packet_age_minutes: `{payload['freshness']['max_packet_age_minutes']}`",
        f"- product_decision_packet: `{payload['source_paths']['product_decision_packet']}`",
        f"- queue_batch_service_remains_default: `{payload['decision']['queue_batch_service_remains_default']}`",
        f"- true_batch_b4_status: `{payload['decision']['true_batch_b4_status']}`",
        f"- do_not_promote_true_batch: `{payload['decision']['do_not_promote_true_batch']}`",
        "",
        "## Packet Summary",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in payload["packet_summary"].items())
    lines.extend(["", "## Remote State", ""])
    for key in [
        "queue_active",
        "queue_enabled",
        "gateway_active",
        "gateway_enabled",
        "gateway_main_pid",
        "listener_pid",
        "openclaw_gateway_active",
        "queue_pending_count",
        "queue_processing_count",
        "health_json",
    ]:
        lines.append(f"- {key}: `{payload['remote_state'].get(key)}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["checks"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that the Dream7B queue-batch default is fresh, healthy, and not shadow-promoted by true-batch artifacts."
    )
    parser.add_argument("--snapshot-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--max-packet-age-minutes", type=float, default=180.0)
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", type=Path, default=Path(r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"))
    parser.add_argument("--known-hosts", type=Path, default=Path(r"C:\Users\zhexu\.ssh\known_hosts"))
    parser.add_argument("--remote-timeout-sec", type=int, default=30)
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path(
            "tmp/product_guardrail_snapshots/dream7b_default_service_freshness_gate_latest.json"
        ),
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path(
            "tmp/product_guardrail_snapshots/dream7b_default_service_freshness_gate_latest.md"
        ),
    )
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_md(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
