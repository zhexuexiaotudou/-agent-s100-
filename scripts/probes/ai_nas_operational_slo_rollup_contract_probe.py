#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_operational_slo_rollup_contract"


REPORT_CONTRACTS = [
    {
        "key": "user_facing_tail_latency",
        "filename": "user_facing_tail_latency.json",
        "required": True,
        "accepted_verdicts": ["ok_ai_nas_user_facing_tail_latency"],
        "metric_paths": {
            "all_p95_ms": ["summary", "all_latency", "p95_ms"],
            "all_p99_ms": ["summary", "all_latency", "p99_ms"],
            "failed_sample_count": ["summary", "failed_sample_count"],
        },
    },
    {
        "key": "continuous_task_soak",
        "filename": "continuous_task_soak.json",
        "required": True,
        "accepted_verdicts": ["ok_ai_nas_continuous_task_soak"],
        "metric_paths": {
            "throughput_jobs_per_s": ["summary", "overall_throughput_jobs_per_s"],
            "queue_wait_p95_ms": ["summary", "overall_queue_wait", "p95_ms"],
            "queue_wait_p99_ms": ["summary", "overall_queue_wait", "p99_ms"],
            "task_p95_ms": ["summary", "overall_task_latency", "p95_ms"],
            "task_p99_ms": ["summary", "overall_task_latency", "p99_ms"],
            "failed_jobs": ["summary", "failed_jobs"],
        },
    },
    {
        "key": "soak_checkpoint_resume",
        "filename": "soak_checkpoint_resume.json",
        "required": True,
        "accepted_verdicts": ["ok_ai_nas_soak_checkpoint_resume"],
        "metric_paths": {
            "recovered_jobs": ["summary", "recovered_jobs"],
            "unfinished_jobs": ["summary", "unfinished_jobs"],
            "duplicate_completed_idempotency_keys": ["summary", "duplicate_completed_idempotency_keys"],
        },
    },
    {
        "key": "queue_backpressure_slo",
        "filename": "queue_backpressure_slo.json",
        "required": True,
        "accepted_verdicts": ["ok_ai_nas_queue_backpressure_slo"],
        "metric_paths": {
            "interactive_queue_wait_p95_ms": ["summary", "interactive_queue_wait", "p95_ms"],
            "interactive_queue_wait_p99_ms": ["summary", "interactive_queue_wait", "p99_ms"],
            "rejected_background": ["summary", "rejected_background"],
            "dead_letter_jobs": ["summary", "dead_letter_jobs"],
            "unfinished_jobs": ["summary", "unfinished_jobs"],
        },
    },
    {
        "key": "index_search_isolation_slo",
        "filename": "index_search_isolation_slo.json",
        "required": True,
        "accepted_verdicts": ["ok_ai_nas_index_search_isolation_slo"],
        "metric_paths": {
            "search_p95_ms": ["summary", "search_latency", "p95_ms"],
            "search_p99_ms": ["summary", "search_latency", "p99_ms"],
            "failed_search_count": ["summary", "failed_search_count"],
            "failed_index_count": ["summary", "failed_index_count"],
        },
    },
    {
        "key": "bpu_headroom_slo",
        "filename": "bpu_headroom_slo.json",
        "required": True,
        "accepted_verdicts": ["ok_ai_nas_bpu_headroom_slo"],
        "metric_paths": {
            "average_utilization_pct": ["summary", "average_utilization_pct"],
            "p95_utilization_pct": ["summary", "p95_utilization_pct"],
            "p99_utilization_pct": ["summary", "p99_utilization_pct"],
            "p01_headroom_pct": ["summary", "p01_headroom_pct"],
            "interactive_wait_p95_ms": ["summary", "interactive_wait_p95_ms"],
            "interactive_wait_p99_ms": ["summary", "interactive_wait_p99_ms"],
            "background_throughput_jobs_per_s": ["summary", "background_throughput_jobs_per_s"],
        },
    },
    {
        "key": "concurrency_stability",
        "filename": "concurrency_stability.json",
        "required": False,
        "accepted_verdicts": ["ok_ai_nas_concurrency_stability", "limited_ai_nas_concurrency_stability"],
        "limited_verdicts": ["limited_ai_nas_concurrency_stability"],
        "metric_paths": {
            "throughput_jobs_per_s": ["summary", "throughput_jobs_per_s"],
            "all_task_p95_ms": ["summary", "all_task_latency", "p95_ms"],
            "all_task_p99_ms": ["summary", "all_task_latency", "p99_ms"],
            "failure_count": ["summary", "failure_count"],
            "dialog_health_ok_count": ["summary", "dialog_health", "ok_count"],
            "dialog_health_error_count": ["summary", "dialog_health", "error_count"],
        },
    },
    {
        "key": "model_service_resilience",
        "filename": "model_service_resilience.json",
        "required": False,
        "accepted_verdicts": ["ok_model_service_resilience_probe", "limited_model_service_resilience_probe"],
        "limited_verdicts": ["limited_model_service_resilience_probe"],
        "metric_paths": {
            "health_ok_count": ["summary", "health_ok_count"],
            "systemctl_active_count": ["summary", "systemctl_active_count"],
            "restart_policy_count": ["summary", "restart_policy_count"],
        },
    },
    {
        "key": "model_service_recovery_drill",
        "filename": "model_service_recovery_drill.json",
        "required": True,
        "accepted_verdicts": ["ok_model_service_recovery_drill"],
        "metric_paths": {
            "recovery_p95_ms": ["summary", "recovery_p95_ms"],
            "recovery_p99_ms": ["summary", "recovery_p99_ms"],
            "recovered_count": ["summary", "recovered_count"],
        },
    },
    {
        "key": "model_service_recovery_manifest",
        "filename": "model_service_recovery_manifest.json",
        "required": True,
        "accepted_verdicts": ["ok_ai_nas_model_service_recovery_manifest"],
        "metric_paths": {
            "proposed_action_count": {"path": ["proposed_actions"], "count": True},
            "blocked_unsafe_action_count": {"path": ["blocked_actions"], "count": True},
            "approval_required": ["approval", "required"],
        },
    },
    {
        "key": "dream7b_gateway_listener_ownership",
        "filename": "dream7b_gateway_listener_ownership.json",
        "required": True,
        "accepted_verdicts": ["ok_dream7b_gateway_listener_ownership"],
        "metric_paths": {
            "gateway_active": ["summary", "gateway_active"],
            "gateway_enabled": ["summary", "gateway_enabled"],
            "listener_matches_systemd_main_pid": ["summary", "listener_matches_systemd_main_pid"],
            "orphan_listener_detected": ["summary", "orphan_listener_detected"],
            "health_ok": ["summary", "health_ok"],
            "gateway_main_pid": ["summary", "gateway_main_pid"],
            "listener_pid": ["summary", "listener_pid"],
        },
    },
    {
        "key": "dream7b_gateway_listener_drift_gate",
        "filename": "dream7b_gateway_listener_drift_gate.json",
        "required": True,
        "accepted_verdicts": ["ok_dream7b_gateway_listener_drift_gate"],
        "metric_paths": {
            "snapshot_found": ["summary", "snapshot_found"],
            "snapshot_ok": ["summary", "snapshot_ok"],
            "live_gateway_active": ["summary", "live_gateway_active"],
            "live_gateway_enabled": ["summary", "live_gateway_enabled"],
            "live_listener_matches_systemd_main_pid": [
                "summary",
                "live_listener_matches_systemd_main_pid",
            ],
            "live_orphan_listener_detected": ["summary", "live_orphan_listener_detected"],
            "live_health_ok": ["summary", "live_health_ok"],
            "snapshot_age_seconds": ["summary", "snapshot_age_seconds"],
            "failure_count": ["summary", "failure_count"],
            "warning_count": ["summary", "warning_count"],
        },
    },
    {
        "key": "dream7b_default_service_freshness_gate",
        "filename": "dream7b_default_service_freshness_gate_latest.json",
        "required": True,
        "accepted_verdicts": ["ok_dream7b_default_service_freshness_gate"],
        "metric_paths": {
            "packet_age_minutes": ["freshness", "packet_age_minutes"],
            "failed_check_count": {"path": ["failed_checks"], "count": True},
            "queue_batch_service_remains_default": [
                "decision",
                "queue_batch_service_remains_default",
            ],
            "do_not_promote_true_batch": ["decision", "do_not_promote_true_batch"],
            "queue_partial_batch_flush_ready": [
                "checks",
                "queue_partial_batch_flush_ready",
            ],
            "queue_partial_batch_flush_probe_or_health_ready": [
                "checks",
                "queue_partial_batch_flush_probe_or_health_ready",
            ],
            "queue_partial_batch_flush_live_summary_state_recorded": [
                "checks",
                "queue_partial_batch_flush_live_summary_state_recorded",
            ],
            "queue_partial_batch_flush_live_summary_ready": [
                "packet_summary",
                "queue_partial_batch_flush_live_summary_ready",
            ],
            "queue_partial_batch_flush_probe_ready": [
                "packet_summary",
                "queue_partial_batch_flush_probe_ready",
            ],
            "queue_partial_batch_flush_health_snapshot_ready": [
                "packet_summary",
                "queue_partial_batch_flush_health_snapshot_ready",
            ],
            "queue_partial_batch_flush_readiness_source": [
                "packet_summary",
                "queue_partial_batch_flush_readiness_source",
            ],
            "queue_partial_batch_probe_run_dir": [
                "packet_summary",
                "queue_partial_batch_probe_run_dir",
            ],
            "queue_partial_batch_probe_ms_per_request": [
                "packet_summary",
                "queue_partial_batch_probe_ms_per_request",
            ],
            "first_response_warning_triage_ok": [
                "checks",
                "first_response_warning_triage_ok",
            ],
            "first_response_warning_triage_starts_no_runtime_or_compile": [
                "checks",
                "first_response_warning_triage_starts_no_runtime_or_compile",
            ],
            "first_response_warning_triage_verdict": [
                "packet_summary",
                "first_response_warning_triage_verdict",
            ],
            "first_response_warning_triaged": [
                "packet_summary",
                "first_response_warning_triaged",
            ],
            "first_response_warning_source_verdict": [
                "packet_summary",
                "first_response_warning_source_verdict",
            ],
            "first_response_warning_quickpath_delta_ms": [
                "packet_summary",
                "first_response_warning_quickpath_delta_ms",
            ],
            "first_response_warning_backend_not_true_batch_work": [
                "packet_summary",
                "first_response_warning_backend_not_true_batch_work",
            ],
            "slo_limited_evidence_triage_ok": [
                "checks",
                "slo_limited_evidence_triage_ok",
            ],
            "slo_limited_evidence_triage_starts_no_runtime_or_compile": [
                "checks",
                "slo_limited_evidence_triage_starts_no_runtime_or_compile",
            ],
            "slo_limited_evidence_triage_verdict": [
                "packet_summary",
                "slo_limited_evidence_triage_verdict",
            ],
            "slo_limited_evidence_triaged": [
                "packet_summary",
                "slo_limited_evidence_triaged",
            ],
            "slo_limited_evidence_release_blocker": [
                "packet_summary",
                "slo_limited_evidence_release_blocker",
            ],
            "slo_limited_evidence_warnings": [
                "packet_summary",
                "slo_limited_evidence_warnings",
            ],
            "slo_limited_concurrency_verdict": [
                "packet_summary",
                "slo_limited_concurrency_verdict",
            ],
            "slo_limited_dialog_health_error_count": [
                "packet_summary",
                "slo_limited_dialog_health_error_count",
            ],
            "per_run_evidence_matrix_verdict": [
                "packet_summary",
                "per_run_evidence_matrix_verdict",
            ],
            "per_run_evidence_matrix_run_count": [
                "packet_summary",
                "per_run_evidence_matrix_run_count",
            ],
            "per_run_evidence_matrix_successful_run_count": [
                "packet_summary",
                "per_run_evidence_matrix_successful_run_count",
            ],
            "per_run_evidence_matrix_failed_run_count": [
                "packet_summary",
                "per_run_evidence_matrix_failed_run_count",
            ],
            "per_run_evidence_matrix_top_segment": [
                "packet_summary",
                "per_run_evidence_matrix_top_segment",
            ],
            "per_run_evidence_matrix_top_segment_rate": [
                "packet_summary",
                "per_run_evidence_matrix_top_segment_rate",
            ],
            "per_run_evidence_matrix_standard_sweep_status": [
                "packet_summary",
                "per_run_evidence_matrix_standard_sweep_status",
            ],
            "per_run_evidence_matrix_ok": [
                "checks",
                "per_run_evidence_matrix_ok",
            ],
            "per_run_evidence_matrix_blocks_standard_sweeps": [
                "checks",
                "per_run_evidence_matrix_blocks_standard_sweeps",
            ],
            "runtime_experiment_gate_uses_per_run_matrix": [
                "checks",
                "runtime_experiment_gate_uses_per_run_matrix",
            ],
            "next_action_pack_uses_per_run_matrix": [
                "checks",
                "next_action_pack_uses_per_run_matrix",
            ],
            "runtime_gate_per_run_matrix_gate_ready": [
                "packet_summary",
                "runtime_gate_per_run_matrix_gate_ready",
            ],
            "runtime_gate_per_run_matrix_top_segment": [
                "packet_summary",
                "runtime_gate_per_run_matrix_top_segment",
            ],
            "runtime_gate_per_run_matrix_standard_sweep_status": [
                "packet_summary",
                "runtime_gate_per_run_matrix_standard_sweep_status",
            ],
            "next_action_pack_per_run_matrix_gate_ready": [
                "packet_summary",
                "next_action_pack_per_run_matrix_gate_ready",
            ],
            "next_action_pack_per_run_matrix_top_segment": [
                "packet_summary",
                "next_action_pack_per_run_matrix_top_segment",
            ],
            "next_action_pack_per_run_matrix_standard_sweep_status": [
                "packet_summary",
                "next_action_pack_per_run_matrix_standard_sweep_status",
            ],
            "nas_inventory_prevents_duplicate_sweeps": [
                "checks",
                "nas_inventory_prevents_duplicate_sweeps",
            ],
            "nas_inventory_b4_json_mirrored": [
                "checks",
                "nas_inventory_b4_json_mirrored",
            ],
            "nas_remote_group_major_report_json_count": [
                "packet_summary",
                "nas_remote_group_major_report_json_count",
            ],
            "nas_remote_b4_group_major_report_json_count": [
                "packet_summary",
                "nas_remote_b4_group_major_report_json_count",
            ],
            "nas_local_b4_json_count": [
                "packet_summary",
                "nas_local_b4_json_count",
            ],
            "nas_b4_remote_json_local_count_match": [
                "packet_summary",
                "nas_b4_remote_json_local_count_match",
            ],
            "workstream_remote_b4_group_major_report_json_count": [
                "packet_summary",
                "workstream_remote_b4_group_major_report_json_count",
            ],
            "workstream_b4_remote_json_local_count_match": [
                "packet_summary",
                "workstream_b4_remote_json_local_count_match",
            ],
            "group_order_partition_prevents_duplicate_sweeps": [
                "checks",
                "group_order_partition_prevents_duplicate_sweeps",
            ],
            "segment_group_schedule_scorecard_ok": [
                "checks",
                "segment_group_schedule_scorecard_ok",
            ],
            "segment_group_schedule_blocks_runtime_compile_sweeps": [
                "checks",
                "segment_group_schedule_blocks_runtime_compile_sweeps",
            ],
            "segment_group_primary_schedule_bottleneck": [
                "packet_summary",
                "segment_group_primary_schedule_bottleneck",
            ],
            "segment_group_primary_code_target": [
                "packet_summary",
                "segment_group_primary_code_target",
            ],
            "segment_group_preferred_group_policy": [
                "packet_summary",
                "segment_group_preferred_group_policy",
            ],
            "segment_group_preferred_inner_order": [
                "packet_summary",
                "segment_group_preferred_inner_order",
            ],
            "segment_group_run_more_standard_sweeps_now": [
                "packet_summary",
                "segment_group_run_more_standard_sweeps_now",
            ],
            "segment_group_run_s100p_runtime_now": [
                "packet_summary",
                "segment_group_run_s100p_runtime_now",
            ],
            "runtime_source_implementation_map_ok": [
                "checks",
                "runtime_source_implementation_map_ok",
            ],
            "runtime_source_implementation_map_blocks_runtime_compile_defaults": [
                "checks",
                "runtime_source_implementation_map_blocks_runtime_compile_defaults",
            ],
            "runtime_source_implementation_map_verdict": [
                "packet_summary",
                "runtime_source_implementation_map_verdict",
            ],
            "runtime_source_pattern_count": [
                "packet_summary",
                "runtime_source_pattern_count",
            ],
            "runtime_source_missing_source_pattern_count": [
                "packet_summary",
                "runtime_source_missing_source_pattern_count",
            ],
            "runtime_source_primary_runtime_refactor_target": [
                "packet_summary",
                "runtime_source_primary_runtime_refactor_target",
            ],
            "runtime_source_s100p_runtime_allowed_now": [
                "packet_summary",
                "runtime_source_s100p_runtime_allowed_now",
            ],
            "runtime_source_compile_start_allowed_now": [
                "packet_summary",
                "runtime_source_compile_start_allowed_now",
            ],
            "runtime_source_runtime_default_change_allowed_now": [
                "packet_summary",
                "runtime_source_runtime_default_change_allowed_now",
            ],
            "runtime_source_standard_sweeps_blocked": [
                "packet_summary",
                "runtime_source_standard_sweeps_blocked",
            ],
            "runtime_refactor_work_order_ok": [
                "checks",
                "runtime_refactor_work_order_ok",
            ],
            "runtime_refactor_work_order_blocks_runtime_compile_defaults": [
                "checks",
                "runtime_refactor_work_order_blocks_runtime_compile_defaults",
            ],
            "hidden_materialize_design_contract_ok": [
                "checks",
                "hidden_materialize_design_contract_ok",
            ],
            "hidden_materialize_design_contract_blocks_runtime_compile_defaults": [
                "checks",
                "hidden_materialize_design_contract_blocks_runtime_compile_defaults",
            ],
            "hidden_materialize_telemetry_contract_ok": [
                "checks",
                "hidden_materialize_telemetry_contract_ok",
            ],
            "hidden_materialize_telemetry_contract_blocks_runtime_compile_defaults": [
                "checks",
                "hidden_materialize_telemetry_contract_blocks_runtime_compile_defaults",
            ],
            "runtime_refactor_work_order_verdict": [
                "packet_summary",
                "runtime_refactor_work_order_verdict",
            ],
            "runtime_refactor_work_order_count": [
                "packet_summary",
                "runtime_refactor_work_order_count",
            ],
            "runtime_refactor_work_order_allowed_local_work_count": [
                "packet_summary",
                "runtime_refactor_work_order_allowed_local_work_count",
            ],
            "runtime_refactor_work_order_source_anchor_missing_count": [
                "packet_summary",
                "runtime_refactor_work_order_source_anchor_missing_count",
            ],
            "runtime_refactor_work_order_default_runtime_change_allowed_now": [
                "packet_summary",
                "runtime_refactor_work_order_default_runtime_change_allowed_now",
            ],
            "runtime_refactor_work_order_s100p_runtime_allowed_now": [
                "packet_summary",
                "runtime_refactor_work_order_s100p_runtime_allowed_now",
            ],
            "runtime_refactor_work_order_compile_start_allowed_now": [
                "packet_summary",
                "runtime_refactor_work_order_compile_start_allowed_now",
            ],
            "hidden_materialize_design_contract_verdict": [
                "packet_summary",
                "hidden_materialize_design_contract_verdict",
            ],
            "hidden_materialize_design_allowed_design_only_count": [
                "packet_summary",
                "hidden_materialize_design_allowed_design_only_count",
            ],
            "hidden_materialize_design_source_anchor_missing_count": [
                "packet_summary",
                "hidden_materialize_design_source_anchor_missing_count",
            ],
            "hidden_materialize_design_current_preallocate_hidden_rejected": [
                "packet_summary",
                "hidden_materialize_design_current_preallocate_hidden_rejected",
            ],
            "hidden_materialize_design_next_design_only_item": [
                "packet_summary",
                "hidden_materialize_design_next_design_only_item",
            ],
            "hidden_materialize_design_next_report_only_item": [
                "packet_summary",
                "hidden_materialize_design_next_report_only_item",
            ],
            "hidden_materialize_design_default_runtime_change_allowed_now": [
                "packet_summary",
                "hidden_materialize_design_default_runtime_change_allowed_now",
            ],
            "hidden_materialize_design_s100p_runtime_allowed_now": [
                "packet_summary",
                "hidden_materialize_design_s100p_runtime_allowed_now",
            ],
            "hidden_materialize_design_compile_start_allowed_now": [
                "packet_summary",
                "hidden_materialize_design_compile_start_allowed_now",
            ],
            "hidden_materialize_telemetry_contract_verdict": [
                "packet_summary",
                "hidden_materialize_telemetry_contract_verdict",
            ],
            "hidden_materialize_telemetry_required_field_count": [
                "packet_summary",
                "hidden_materialize_telemetry_required_field_count",
            ],
            "hidden_materialize_telemetry_source_anchor_missing_count": [
                "packet_summary",
                "hidden_materialize_telemetry_source_anchor_missing_count",
            ],
            "hidden_materialize_telemetry_source_ready": [
                "packet_summary",
                "hidden_materialize_telemetry_source_ready",
            ],
            "hidden_materialize_telemetry_default_runtime_change_allowed_now": [
                "packet_summary",
                "hidden_materialize_telemetry_default_runtime_change_allowed_now",
            ],
            "hidden_materialize_telemetry_s100p_runtime_allowed_now": [
                "packet_summary",
                "hidden_materialize_telemetry_s100p_runtime_allowed_now",
            ],
            "hidden_materialize_telemetry_compile_start_allowed_now": [
                "packet_summary",
                "hidden_materialize_telemetry_compile_start_allowed_now",
            ],
            "scheduler_overhead_deprioritizes_python_gap_tuning": [
                "checks",
                "scheduler_overhead_deprioritizes_python_gap_tuning",
            ],
            "runtime_instrumentation_ready": [
                "checks",
                "runtime_instrumentation_ready",
            ],
            "runtime_instrumentation_contract_verdict": [
                "packet_summary",
                "runtime_instrumentation_contract_verdict",
            ],
            "runtime_instrumentation_deployment_verdict": [
                "packet_summary",
                "runtime_instrumentation_deployment_verdict",
            ],
            "hbm_load_accounting_contract_ok": [
                "checks",
                "hbm_load_accounting_contract_ok",
            ],
            "hbm_load_accounting_contract_verdict": [
                "packet_summary",
                "hbm_load_accounting_contract_verdict",
            ],
            "hbm_per_segment_load_accounting_ready": [
                "packet_summary",
                "hbm_per_segment_load_accounting_ready",
            ],
            "hbm_group_load_accounting_ready": [
                "packet_summary",
                "hbm_group_load_accounting_ready",
            ],
            "hbm_prewarm_accounting_ready": [
                "packet_summary",
                "hbm_prewarm_accounting_ready",
            ],
            "hbm_timing_summary_accounts_load_and_prewarm": [
                "packet_summary",
                "hbm_timing_summary_accounts_load_and_prewarm",
            ],
            "bottleneck_closure_model_ok": [
                "checks",
                "bottleneck_closure_model_ok",
            ],
            "bottleneck_closure_model_verdict": [
                "packet_summary",
                "bottleneck_closure_model_verdict",
            ],
            "bottleneck_closure_primary_next_code_target": [
                "packet_summary",
                "bottleneck_closure_primary_next_code_target",
            ],
            "bottleneck_closure_final_logits_projection_saved_ms_per_request": [
                "packet_summary",
                "bottleneck_closure_final_logits_projection_saved_ms_per_request",
            ],
            "bottleneck_closure_hbm_group_load_ms_per_request": [
                "packet_summary",
                "bottleneck_closure_hbm_group_load_ms_per_request",
            ],
            "bottleneck_closure_projection_is_not_bpu_promotion_proof": [
                "packet_summary",
                "bottleneck_closure_projection_is_not_bpu_promotion_proof",
            ],
            "remote_queue_active_enabled": ["checks", "remote_queue_active_enabled"],
            "remote_gateway_active_enabled": ["checks", "remote_gateway_active_enabled"],
            "remote_listener_matches_gateway_pid": [
                "checks",
                "remote_listener_matches_gateway_pid",
            ],
            "remote_health_ok": ["checks", "remote_health_ok"],
        },
    },
    {
        "key": "dream7b_first_response_slo_tier_guard",
        "filename": "dream7b_first_response_slo_tier_guard_latest.json",
        "required": True,
        "accepted_verdicts": ["ok_dream7b_first_response_slo_tier_guard"],
        "metric_paths": {
            "health_ready": ["tiers", "health", "ready"],
            "fast_path_ready": ["tiers", "fast_path_first_content", "ready"],
            "fast_path_max_first_content_ms": [
                "tiers",
                "fast_path_first_content",
                "max_first_content_ms",
            ],
            "sse_progress_ready": ["tiers", "sse_progress", "ready"],
            "sse_first_progress_p50_ms": [
                "tiers",
                "sse_progress",
                "first_progress_p50_ms",
            ],
            "backend_first_content_tracked_separately": [
                "tiers",
                "backend_first_content",
                "tracked_separately",
            ],
            "backend_explicit_first_content_p50_ms": [
                "tiers",
                "backend_first_content",
                "explicit_first_content_p50_ms",
            ],
            "backend_first_content_latency_is_not_true_batch_work": [
                "decision",
                "backend_first_content_latency_is_not_true_batch_work",
            ],
            "queue_batch_service_remains_default": [
                "decision",
                "queue_batch_service_remains_default",
            ],
            "runtime_started": ["audit", "runtime_started"],
            "compile_started": ["audit", "compile_started"],
            "failed_check_count": {"path": ["failed_checks"], "count": True},
        },
    },
    {
        "key": "dream7b_first_response_warning_triage",
        "filename": "dream7b_first_response_warning_triage_latest.json",
        "required": True,
        "accepted_verdicts": ["ok_dream7b_first_response_warning_triage"],
        "metric_paths": {
            "source_warning_verdict": ["summary", "source_warning_verdict"],
            "source_warning_count": ["summary", "source_warning_count"],
            "warning_is_product_triaged": ["decision", "warning_is_product_triaged"],
            "first_content_p50_ms": ["summary", "first_content_p50_ms"],
            "quickpath_first_content_p50_ms": [
                "summary",
                "quickpath_first_content_p50_ms",
            ],
            "quickpath_delta_ms": ["summary", "quickpath_delta_ms"],
            "fast_path_max_first_content_ms": [
                "summary",
                "fast_path_max_first_content_ms",
            ],
            "backend_first_content_tracked_separately": [
                "summary",
                "backend_first_content_tracked_separately",
            ],
            "backend_first_content_latency_is_not_true_batch_work": [
                "summary",
                "backend_first_content_latency_is_not_true_batch_work",
            ],
            "queue_batch_service_remains_default": [
                "decision",
                "queue_batch_service_remains_default",
            ],
            "do_not_promote_true_batch_for_first_response": [
                "decision",
                "do_not_promote_true_batch_for_first_response",
            ],
            "runtime_started": ["audit", "runtime_started"],
            "compile_started": ["audit", "compile_started"],
            "failed_check_count": {"path": ["failed_checks"], "count": True},
        },
    },
]


def parse_report_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_json(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def report_sort_key(path: Path) -> tuple[float, float, str]:
    payload = read_json(path) or {}
    generated_at = parse_report_time(payload.get("generated_at"))
    generated_ts = generated_at.timestamp() if generated_at else 0.0
    try:
        mtime_ts = path.stat().st_mtime
    except OSError:
        mtime_ts = 0.0
    return generated_ts, mtime_ts, str(path)


def default_evidence_roots(report_root: Path) -> list[Path]:
    roots = [report_root]
    tmp_root = Path("tmp")
    if tmp_root.exists():
        roots.append(tmp_root)
    return roots


def latest_report(evidence_roots: list[Path], filename: str) -> dict:
    candidates = []
    for root in evidence_roots:
        if not root.exists():
            continue
        try:
            candidates.extend(path for path in root.rglob(filename) if path.is_file())
        except OSError:
            continue
    if not candidates:
        return {
            "found": False,
            "filename": filename,
            "path": None,
            "verdict": None,
            "generated_at": None,
            "selection_policy": "generated_at_then_mtime",
            "payload": None,
        }
    selected = max(candidates, key=report_sort_key)
    payload = read_json(selected)
    return {
        "found": payload is not None,
        "filename": filename,
        "path": str(selected),
        "verdict": payload.get("verdict") if payload else None,
        "generated_at": payload.get("generated_at") if payload else None,
        "selection_policy": "generated_at_then_mtime",
        "payload": payload,
    }


def nested_get(payload: dict, path: list[str]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def metric_value(payload: dict, spec: Any) -> Any:
    if isinstance(spec, dict):
        value = nested_get(payload, spec.get("path") or [])
        if spec.get("count"):
            return len(value) if isinstance(value, list) else None
        return value
    return nested_get(payload, spec)


def evaluate_contract(contract: dict, evidence_roots: list[Path]) -> dict:
    report = latest_report(evidence_roots, contract["filename"])
    payload = report.get("payload") or {}
    verdict = report.get("verdict")
    accepted = bool(report.get("found")) and verdict in contract["accepted_verdicts"]
    limited = verdict in contract.get("limited_verdicts", [])
    metrics = {
        metric_name: metric_value(payload, path)
        for metric_name, path in contract.get("metric_paths", {}).items()
    }
    blockers = []
    warnings = []
    if contract.get("required") and not report.get("found"):
        blockers.append(f"{contract['key']}:report_missing")
    elif contract.get("required") and not accepted:
        blockers.append(f"{contract['key']}:verdict_not_accepted:{verdict}")
    elif not contract.get("required") and not report.get("found"):
        warnings.append(f"{contract['key']}:observational_report_missing")
    elif not accepted:
        warnings.append(f"{contract['key']}:observational_verdict_not_accepted:{verdict}")
    if limited:
        warnings.append(f"{contract['key']}:limited_production_evidence")
    if contract.get("required") and accepted:
        for metric_name, metric in metrics.items():
            if metric is None:
                blockers.append(f"{contract['key']}:metric_missing:{metric_name}")
    return {
        "key": contract["key"],
        "required": bool(contract.get("required")),
        "accepted": accepted,
        "limited": limited,
        "report": {key: value for key, value in report.items() if key != "payload"},
        "metrics": metrics,
        "blockers": blockers,
        "warnings": warnings,
    }


def build_scorecard(items: list[dict]) -> dict:
    by_key = {item["key"]: item for item in items}
    return {
        "tail_latency": (by_key.get("user_facing_tail_latency") or {}).get("metrics", {}),
        "continuous_throughput": (by_key.get("continuous_task_soak") or {}).get("metrics", {}),
        "queue_backpressure": (by_key.get("queue_backpressure_slo") or {}).get("metrics", {}),
        "index_search_concurrency": (by_key.get("index_search_isolation_slo") or {}).get("metrics", {}),
        "mixed_concurrency_stability": (by_key.get("concurrency_stability") or {}).get("metrics", {}),
        "bpu_headroom": (by_key.get("bpu_headroom_slo") or {}).get("metrics", {}),
        "model_recovery": {
            "resilience": (by_key.get("model_service_resilience") or {}).get("metrics", {}),
            "drill": (by_key.get("model_service_recovery_drill") or {}).get("metrics", {}),
            "manifest": (by_key.get("model_service_recovery_manifest") or {}).get("metrics", {}),
            "dream7b_gateway_listener_ownership": (
                by_key.get("dream7b_gateway_listener_ownership") or {}
            ).get("metrics", {}),
            "dream7b_gateway_listener_drift_gate": (
                by_key.get("dream7b_gateway_listener_drift_gate") or {}
            ).get("metrics", {}),
            "dream7b_default_service_freshness_gate": (
                by_key.get("dream7b_default_service_freshness_gate") or {}
            ).get("metrics", {}),
            "dream7b_first_response_slo_tier_guard": (
                by_key.get("dream7b_first_response_slo_tier_guard") or {}
            ).get("metrics", {}),
        },
        "dream7b_runtime_duplicate_guards": {
            "default_service_freshness_gate": (
                by_key.get("dream7b_default_service_freshness_gate") or {}
            ).get("metrics", {}),
            "first_response_slo_tier_guard": (
                by_key.get("dream7b_first_response_slo_tier_guard") or {}
            ).get("metrics", {}),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS operational SLO rollup contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--evidence-root", action="append", type=Path, default=[])
    args = parser.parse_args()

    evidence_roots = args.evidence_root or default_evidence_roots(args.report_root)
    run_dir = ensure_report_dir(args.report_root, "operational_slo_rollup_contract")
    items = [evaluate_contract(contract, evidence_roots) for contract in REPORT_CONTRACTS]
    blockers = [blocker for item in items for blocker in item["blockers"]]
    warnings = [warning for item in items for warning in item["warnings"]]
    required_items = [item for item in items if item["required"]]
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_operational_slo_rollup_contract" if not blockers else "failed_ai_nas_operational_slo_rollup_contract",
        "scope": "operator-facing rollup for P95/P99 latency, continuous throughput, queue backpressure, index/search concurrency, BPU headroom, and model-service recovery evidence",
        "evidence_roots": [str(root) for root in evidence_roots],
        "contracts": items,
        "scorecard": build_scorecard(items),
        "summary": {
            "contract_count": len(items),
            "required_contract_count": len(required_items),
            "required_accepted_count": sum(1 for item in required_items if item["accepted"]),
            "observational_contract_count": len(items) - len(required_items),
            "observational_accepted_count": sum(1 for item in items if not item["required"] and item["accepted"]),
            "limited_evidence_count": sum(1 for item in items if item["limited"]),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "blockers": blockers,
            "warnings": warnings,
        },
        "operator_priorities": [
            "Keep interactive P95/P99 latency and queue wait ahead of average BPU utilization.",
            "Treat 93-95 percent average BPU utilization with headroom as healthier than a 100 percent saturation target.",
            "Use this rollup as the production operations view; use owning probe reports for detailed root cause.",
            "Promote limited service-health observations to hard evidence only after real NAS/model/OpenClaw services are installed and monitored.",
            "Keep Dream7B queue-batch as the default unless the freshness gate and product packet both explicitly allow a promotion.",
        ],
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "download_performed": False,
            "network_call_performed": False,
            "service_restart_performed": False,
            "kill_performed": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON operational SLO rollup reports only",
        },
    }
    json_path = run_dir / "operational_slo_rollup_contract.json"
    md_path = run_dir / "operational_slo_rollup_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Operational SLO Rollup Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- required_accepted_count: `{payload['summary']['required_accepted_count']}/{payload['summary']['required_contract_count']}`",
        f"- limited_evidence_count: `{payload['summary']['limited_evidence_count']}`",
        f"- blocker_count: `{payload['summary']['blocker_count']}`",
        f"- warning_count: `{payload['summary']['warning_count']}`",
        "- policy: report-only rollup; no downloads, network calls, service restarts, kills, deletes, moves, overwrites, or Personal source mutation",
        "",
        "## Contracts",
        "",
    ]
    for item in items:
        lines.append(
            f"- `{item['key']}` required `{item['required']}` accepted `{item['accepted']}` "
            f"limited `{item['limited']}` verdict `{item['report']['verdict']}`"
        )
    lines.extend(["", "## Blockers", ""])
    if not blockers:
        lines.append("- No required operational SLO rollup blocker detected.")
    for blocker in blockers:
        lines.append(f"- {blocker}")
    lines.extend(["", "## Warnings", ""])
    if not warnings:
        lines.append("- No operational SLO rollup warning detected.")
    for warning in warnings:
        lines.append(f"- {warning}")
    lines.extend(["", "## Scorecard", ""])
    for key, value in payload["scorecard"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
