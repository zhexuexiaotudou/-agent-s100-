#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/run_allowlisted_tool.sh list
  scripts/run_allowlisted_tool.sh openclaw_status_probe [output_dir]
  scripts/run_allowlisted_tool.sh nas_discovery_probe [output_dir]
  scripts/run_allowlisted_tool.sh nas_link_blocker_probe [output_dir] [target_ip]
  scripts/run_allowlisted_tool.sh infrastructure_gate_probe [workspace_dir] [report_dir]
  scripts/run_allowlisted_tool.sh ros2_status_probe [output_dir]
  scripts/run_allowlisted_tool.sh sandbox_status_probe [output_dir]
  scripts/run_allowlisted_tool.sh sandbox_isolation_smoke_probe [output_dir]
  scripts/run_allowlisted_tool.sh security_audit_probe [output_dir]
  scripts/run_allowlisted_tool.sh service_policy_probe [output_dir]
  scripts/run_allowlisted_tool.sh service_hardening_plan_probe [output_dir]
  scripts/run_allowlisted_tool.sh service_convergence_decision_probe [input_dir] [report_dir]
  scripts/run_allowlisted_tool.sh service_confirmation_template_probe [report_dir]
  scripts/run_allowlisted_tool.sh service_execution_preflight_probe [report_dir] [config_file]
  scripts/run_allowlisted_tool.sh stability_snapshot_probe [output_dir]
  scripts/run_allowlisted_tool.sh stability_summary_probe [input_dir] [report_dir]
  scripts/run_allowlisted_tool.sh stability_checkpoint_probe [input_dir] [report_dir] [target_hours] [max_gap_hours]
  scripts/run_allowlisted_tool.sh image_caption_probe [photos_dir] [report_dir]
  scripts/run_allowlisted_tool.sh vision_caption_readiness_probe [photos_dir] [report_dir]
  scripts/run_allowlisted_tool.sh dream7b_readiness_probe [report_dir]
  scripts/run_allowlisted_tool.sh dream7b_config_template_probe [report_dir]
  scripts/run_allowlisted_tool.sh dream7b_smoke_probe [report_dir] [config_file]
  scripts/run_allowlisted_tool.sh home_assistant_config_template_probe [report_dir]
  scripts/run_allowlisted_tool.sh home_assistant_status_probe [output_dir]
  scripts/run_allowlisted_tool.sh external_input_gate_probe [workspace_dir] [report_dir]
  scripts/run_allowlisted_tool.sh control_action_template_probe [report_dir]
  scripts/run_allowlisted_tool.sh control_action_policy_probe [output_dir]
  scripts/run_allowlisted_tool.sh operator_review_gate_probe [workspace_dir] [report_dir]
  scripts/run_allowlisted_tool.sh browser_smoke_probe [report_dir]
  scripts/run_allowlisted_tool.sh dataset_card_inventory_probe [dataset_root] [report_dir]
  scripts/run_allowlisted_tool.sh rosbag_snapshot_probe [dataset_dir] [report_dir]
  scripts/run_allowlisted_tool.sh rosbag_session_probe [dataset_dir] [report_dir]
  scripts/run_allowlisted_tool.sh rosbag_capture_policy_probe [output_dir]
  scripts/run_allowlisted_tool.sh rosbag_named_capture_request_probe [report_dir]
  scripts/run_allowlisted_tool.sh rosbag_named_capture_probe [dataset_dir] [report_dir]
  scripts/run_allowlisted_tool.sh experiment_report_probe [report_dir]
  scripts/run_allowlisted_tool.sh log_diagnose [log_dir] [output_dir]
  scripts/run_allowlisted_tool.sh index_documents [documents_dir] [report_dir]
  scripts/run_allowlisted_tool.sh document_daily_summary_probe [documents_dir] [report_dir]
  scripts/run_allowlisted_tool.sh openclaw_entry_demo_probe [report_dir]
  scripts/run_allowlisted_tool.sh ai_nas_movie_sort_demo_probe [demo_root] [report_dir]
  scripts/run_allowlisted_tool.sh ai_nas_personal_inventory
  scripts/run_allowlisted_tool.sh ai_nas_personal_inventory_probe
  scripts/run_allowlisted_tool.sh ai_nas_index_status
  scripts/run_allowlisted_tool.sh ai_nas_index_status_probe
  scripts/run_allowlisted_tool.sh ai_nas_index_daemon_readiness
  scripts/run_allowlisted_tool.sh ai_nas_index_daemon_readiness_probe
  scripts/run_allowlisted_tool.sh ai_nas_index_daemon_smoke
  scripts/run_allowlisted_tool.sh ai_nas_index_daemon_smoke_probe
  scripts/run_allowlisted_tool.sh ai_nas_index_daemon_resident
  scripts/run_allowlisted_tool.sh ai_nas_index_daemon_resident_probe
  scripts/run_allowlisted_tool.sh ai_nas_index_systemd_daemon_install
  scripts/run_allowlisted_tool.sh ai_nas_index_systemd_daemon_install_probe
  scripts/run_allowlisted_tool.sh ai_nas_index_rename_detection
  scripts/run_allowlisted_tool.sh ai_nas_index_rename_detection_probe
  scripts/run_allowlisted_tool.sh ai_nas_index_observability_contract
  scripts/run_allowlisted_tool.sh ai_nas_index_observability_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_sqlite_index_integrity_contract
  scripts/run_allowlisted_tool.sh ai_nas_sqlite_index_integrity_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_incremental_scan_efficiency_contract
  scripts/run_allowlisted_tool.sh ai_nas_incremental_scan_efficiency_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_index_search_isolation_slo
  scripts/run_allowlisted_tool.sh ai_nas_index_search_isolation_slo_probe
  scripts/run_allowlisted_tool.sh ai_nas_perf_benchmark
  scripts/run_allowlisted_tool.sh ai_nas_perf_benchmark_probe
  scripts/run_allowlisted_tool.sh ai_nas_concurrency_stability
  scripts/run_allowlisted_tool.sh ai_nas_concurrency_stability_probe
  scripts/run_allowlisted_tool.sh ai_nas_continuous_task_soak
  scripts/run_allowlisted_tool.sh ai_nas_continuous_task_soak_probe
  scripts/run_allowlisted_tool.sh ai_nas_nas_backed_long_soak
  scripts/run_allowlisted_tool.sh ai_nas_nas_backed_long_soak_probe
  scripts/run_allowlisted_tool.sh ai_nas_soak_checkpoint_resume
  scripts/run_allowlisted_tool.sh ai_nas_soak_checkpoint_resume_probe
  scripts/run_allowlisted_tool.sh ai_nas_queue_backpressure_slo
  scripts/run_allowlisted_tool.sh ai_nas_queue_backpressure_slo_probe
  scripts/run_allowlisted_tool.sh ai_nas_user_facing_tail_latency
  scripts/run_allowlisted_tool.sh ai_nas_user_facing_tail_latency_probe
  scripts/run_allowlisted_tool.sh ai_nas_bpu_headroom_slo
  scripts/run_allowlisted_tool.sh ai_nas_bpu_headroom_slo_probe
  scripts/run_allowlisted_tool.sh ai_nas_allowlist_governance_audit
  scripts/run_allowlisted_tool.sh ai_nas_allowlist_governance_audit_probe
  scripts/run_allowlisted_tool.sh ai_nas_task_queue
  scripts/run_allowlisted_tool.sh ai_nas_task_queue_probe
  scripts/run_allowlisted_tool.sh ai_nas_case_packet
  scripts/run_allowlisted_tool.sh ai_nas_case_packet_probe
  scripts/run_allowlisted_tool.sh ai_nas_appliance_experience_acceptance
  scripts/run_allowlisted_tool.sh ai_nas_appliance_experience_acceptance_probe
  scripts/run_allowlisted_tool.sh ai_nas_operator_portal_contract
  scripts/run_allowlisted_tool.sh ai_nas_operator_portal_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_production_dependency_bundle
  scripts/run_allowlisted_tool.sh ai_nas_production_dependency_bundle_probe
  scripts/run_allowlisted_tool.sh ai_nas_production_blocker_runbook_contract
  scripts/run_allowlisted_tool.sh ai_nas_production_blocker_runbook_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_goal_completion_audit
  scripts/run_allowlisted_tool.sh ai_nas_goal_completion_audit_probe
  scripts/run_allowlisted_tool.sh ai_nas_goal_completion_finalizer
  scripts/run_allowlisted_tool.sh ai_nas_goal_completion_finalizer_probe
  scripts/run_allowlisted_tool.sh ai_nas_evidence_freshness_contract
  scripts/run_allowlisted_tool.sh ai_nas_evidence_freshness_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_portable_nas_adapter_contract
  scripts/run_allowlisted_tool.sh ai_nas_portable_nas_adapter_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_production_readiness_gate
  scripts/run_allowlisted_tool.sh ai_nas_production_readiness_gate_probe
  scripts/run_allowlisted_tool.sh ai_nas_search_evidence_contract
  scripts/run_allowlisted_tool.sh ai_nas_search_evidence_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_search_confidence_calibration_contract
  scripts/run_allowlisted_tool.sh ai_nas_search_confidence_calibration_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_multimodal_intent_routing_contract
  scripts/run_allowlisted_tool.sh ai_nas_multimodal_intent_routing_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_semantic_query_acceptance
  scripts/run_allowlisted_tool.sh ai_nas_semantic_query_acceptance_probe
  scripts/run_allowlisted_tool.sh ai_nas_action_approval_manifest
  scripts/run_allowlisted_tool.sh ai_nas_action_approval_manifest_probe
  scripts/run_allowlisted_tool.sh ai_nas_action_manifest_integrity
  scripts/run_allowlisted_tool.sh ai_nas_action_manifest_integrity_probe
  scripts/run_allowlisted_tool.sh ai_nas_operator_approval_inbox
  scripts/run_allowlisted_tool.sh ai_nas_operator_approval_inbox_probe
  scripts/run_allowlisted_tool.sh ai_nas_action_execute_copy
  scripts/run_allowlisted_tool.sh ai_nas_action_execute_copy_probe
  scripts/run_allowlisted_tool.sh ai_nas_action_rollback_copy
  scripts/run_allowlisted_tool.sh ai_nas_action_rollback_copy_probe
  scripts/run_allowlisted_tool.sh ai_nas_destructive_action_governance
  scripts/run_allowlisted_tool.sh ai_nas_destructive_action_governance_probe
  scripts/run_allowlisted_tool.sh ai_nas_audit_trail_contract
  scripts/run_allowlisted_tool.sh ai_nas_audit_trail_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_permission_aware_search
  scripts/run_allowlisted_tool.sh ai_nas_permission_aware_search_probe
  scripts/run_allowlisted_tool.sh ai_nas_acl_mapping_readiness
  scripts/run_allowlisted_tool.sh ai_nas_acl_mapping_readiness_probe
  scripts/run_allowlisted_tool.sh ai_nas_evidence_report
  scripts/run_allowlisted_tool.sh ai_nas_evidence_report_probe
  scripts/run_allowlisted_tool.sh ai_nas_embedding_search
  scripts/run_allowlisted_tool.sh ai_nas_embedding_search_probe
  scripts/run_allowlisted_tool.sh ai_nas_embedding_backend_readiness
  scripts/run_allowlisted_tool.sh ai_nas_embedding_backend_readiness_probe
  scripts/run_allowlisted_tool.sh ai_nas_embedding_runtime_contract
  scripts/run_allowlisted_tool.sh ai_nas_embedding_runtime_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_model_service_resilience
  scripts/run_allowlisted_tool.sh ai_nas_model_service_resilience_probe
  scripts/run_allowlisted_tool.sh ai_nas_model_service_recovery_drill
  scripts/run_allowlisted_tool.sh ai_nas_model_service_recovery_drill_probe
  scripts/run_allowlisted_tool.sh ai_nas_model_service_recovery_manifest
  scripts/run_allowlisted_tool.sh ai_nas_model_service_recovery_manifest_probe
  scripts/run_allowlisted_tool.sh ai_nas_model_service_real_recovery_drill [manifest_json] [approval_phrase] [--execute]
  scripts/run_allowlisted_tool.sh ai_nas_model_service_real_recovery_drill_probe [manifest_json] [approval_phrase] [--execute]
  scripts/run_allowlisted_tool.sh ai_nas_ocr_runtime_contract
  scripts/run_allowlisted_tool.sh ai_nas_ocr_runtime_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_ocr_readiness
  scripts/run_allowlisted_tool.sh ai_nas_ocr_readiness_probe
  scripts/run_allowlisted_tool.sh ai_nas_ocr_extract
  scripts/run_allowlisted_tool.sh ai_nas_ocr_extract_probe
  scripts/run_allowlisted_tool.sh ai_nas_document_pipeline_acceptance
  scripts/run_allowlisted_tool.sh ai_nas_document_pipeline_acceptance_probe
  scripts/run_allowlisted_tool.sh ai_nas_file_search
  scripts/run_allowlisted_tool.sh ai_nas_file_search_probe
  scripts/run_allowlisted_tool.sh ai_nas_folder_rag
  scripts/run_allowlisted_tool.sh ai_nas_folder_rag_probe
  scripts/run_allowlisted_tool.sh ai_nas_folder_rag_grounding_contract
  scripts/run_allowlisted_tool.sh ai_nas_folder_rag_grounding_contract_probe
  scripts/run_allowlisted_tool.sh ai_nas_folder_summary
  scripts/run_allowlisted_tool.sh ai_nas_folder_summary_probe
  scripts/run_allowlisted_tool.sh ai_nas_duplicate_report
  scripts/run_allowlisted_tool.sh ai_nas_duplicate_report_probe
  scripts/run_allowlisted_tool.sh ai_nas_photo_similarity
  scripts/run_allowlisted_tool.sh ai_nas_photo_similarity_probe
  scripts/run_allowlisted_tool.sh ai_nas_image_embedding_extract
  scripts/run_allowlisted_tool.sh ai_nas_image_embedding_extract_probe
  scripts/run_allowlisted_tool.sh ai_nas_photo_semantic_search
  scripts/run_allowlisted_tool.sh ai_nas_photo_semantic_search_probe
  scripts/run_allowlisted_tool.sh ai_nas_photo_pipeline_acceptance
  scripts/run_allowlisted_tool.sh ai_nas_photo_pipeline_acceptance_probe
  scripts/run_allowlisted_tool.sh ai_nas_photo_privacy_governance
  scripts/run_allowlisted_tool.sh ai_nas_photo_privacy_governance_probe
  scripts/run_allowlisted_tool.sh ai_nas_movie_sort_enhanced
  scripts/run_allowlisted_tool.sh ai_nas_movie_sort_enhanced_probe
  scripts/run_allowlisted_tool.sh personal_data_sort_probe [share_name] [source_root] [sorted_root] [report_dir]
  scripts/run_allowlisted_tool.sh personal_data_sort_dry_run_probe [share_name] [source_root] [sorted_root] [report_dir]
  scripts/run_allowlisted_tool.sh baseline_status_probe [workspace_dir] [report_dir]
  scripts/run_allowlisted_tool.sh baseline_gap_decision_probe [nas_root] [report_dir]
  scripts/run_allowlisted_tool.sh baseline_acceptance_probe [nas_root] [report_dir]
  scripts/run_allowlisted_tool.sh baseline_acceptance_trend_probe [nas_root] [report_dir]
  scripts/run_allowlisted_tool.sh baseline_next_action_queue_probe [workspace_dir] [report_dir] [audit_decision]
  scripts/run_allowlisted_tool.sh baseline_evidence_manifest_probe [nas_root] [report_dir]
  scripts/run_allowlisted_tool.sh teacher_baseline_briefing_probe [nas_root] [report_dir]

Only explicitly allowlisted tool IDs can be executed. This script never accepts
arbitrary script paths.
EOF
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "$script_dir/.." && pwd)"

tool_id="${1:-}"
if [[ -z "$tool_id" ]]; then
  usage >&2
  exit 2
fi

case "$tool_id" in
  list)
    cat <<'EOF'
openclaw_status_probe  Read-only OpenClaw/network/NAS status probe
nas_discovery_probe  Read-only passive NAS/network discovery for A-003
nas_link_blocker_probe  Read-only targeted NAS link blocker evidence for A-003/B-001
infrastructure_gate_probe  Read-only A-003/A-006/B-001 infrastructure packet gate
log_diagnose           Read-only log error summary report
index_documents        Read-only document index report
document_daily_summary_probe  Read-only deterministic daily document summary
openclaw_entry_demo_probe  Bounded teacher demo evidence for S100P OpenClaw entry and NAS persistence
ai_nas_movie_sort_demo_probe  Bounded AI NAS demo that sorts sample movie files by type inside the demo workspace
ai_nas_personal_inventory  AI-NAS MVP Personal inventory, JSON index, and Markdown report
ai_nas_personal_inventory_probe  Alias for ai_nas_personal_inventory
ai_nas_index_status  AI-NAS MVP SQLite/FTS index status and recent changes report
ai_nas_index_status_probe  Alias for ai_nas_index_status
ai_nas_index_daemon_readiness  AI-NAS MVP background index daemon readiness report
ai_nas_index_daemon_readiness_probe  Alias for ai_nas_index_daemon_readiness
ai_nas_index_daemon_smoke  AI-NAS MVP bounded index daemon change-detection smoke
ai_nas_index_daemon_smoke_probe  Alias for ai_nas_index_daemon_smoke
ai_nas_index_daemon_resident  AI-NAS MVP bounded resident index daemon child-process probe
ai_nas_index_daemon_resident_probe  Alias for ai_nas_index_daemon_resident
ai_nas_index_systemd_daemon_install  AI-NAS production systemd resident index daemon install verification
ai_nas_index_systemd_daemon_install_probe  Alias for ai_nas_index_systemd_daemon_install
ai_nas_index_rename_detection  AI-NAS bounded rename/move detection acceptance
ai_nas_index_rename_detection_probe  Alias for ai_nas_index_rename_detection
ai_nas_index_observability_contract  AI-NAS SQLite index status observability contract
ai_nas_index_observability_contract_probe  Alias for ai_nas_index_observability_contract
ai_nas_sqlite_index_integrity_contract  AI-NAS SQLite/FTS integrity and orphan cleanup contract
ai_nas_sqlite_index_integrity_contract_probe  Alias for ai_nas_sqlite_index_integrity_contract
ai_nas_incremental_scan_efficiency_contract  AI-NAS incremental SQLite/FTS scan efficiency contract
ai_nas_incremental_scan_efficiency_contract_probe  Alias for ai_nas_incremental_scan_efficiency_contract
ai_nas_index_search_isolation_slo  AI-NAS bounded index/search isolation SLO acceptance
ai_nas_index_search_isolation_slo_probe  Alias for ai_nas_index_search_isolation_slo
ai_nas_perf_benchmark  AI-NAS MVP P95/P99 throughput and concurrent index/search benchmark
ai_nas_perf_benchmark_probe  Alias for ai_nas_perf_benchmark
ai_nas_concurrency_stability  AI-NAS MVP concurrent index/search/dialog-health stability report
ai_nas_concurrency_stability_probe  Alias for ai_nas_concurrency_stability
ai_nas_continuous_task_soak  AI-NAS MVP bounded continuous multi-wave task soak
ai_nas_continuous_task_soak_probe  Alias for ai_nas_continuous_task_soak
ai_nas_nas_backed_long_soak  AI-NAS production NAS-backed long soak over real Personal data
ai_nas_nas_backed_long_soak_probe  Alias for ai_nas_nas_backed_long_soak
ai_nas_soak_checkpoint_resume  AI-NAS interrupted soak checkpoint/resume contract
ai_nas_soak_checkpoint_resume_probe  Alias for ai_nas_soak_checkpoint_resume
ai_nas_queue_backpressure_slo  AI-NAS queue backpressure and interactive SLO acceptance
ai_nas_queue_backpressure_slo_probe  Alias for ai_nas_queue_backpressure_slo
ai_nas_user_facing_tail_latency  AI-NAS user-facing P95/P99 tail latency and grounding contract
ai_nas_user_facing_tail_latency_probe  Alias for ai_nas_user_facing_tail_latency
ai_nas_bpu_headroom_slo  AI-NAS BPU headroom and queue scheduling SLO contract
ai_nas_bpu_headroom_slo_probe  Alias for ai_nas_bpu_headroom_slo
ai_nas_operational_slo_rollup_contract  AI-NAS operational SLO rollup across latency, queue, throughput, concurrency, BPU headroom, and recovery evidence
ai_nas_operational_slo_rollup_contract_probe  Alias for ai_nas_operational_slo_rollup_contract
ai_nas_allowlist_governance_audit  AI-NAS MVP allowlist governance metadata audit
ai_nas_allowlist_governance_audit_probe  Alias for ai_nas_allowlist_governance_audit
ai_nas_task_queue  AI-NAS MVP persistent task queue and crash recovery probe
ai_nas_task_queue_probe  Alias for ai_nas_task_queue
ai_nas_case_packet  AI-NAS MVP mixed evidence case packet report
ai_nas_case_packet_probe  Alias for ai_nas_case_packet
ai_nas_appliance_experience_acceptance  AI-NAS MVP end-to-end appliance experience acceptance
ai_nas_appliance_experience_acceptance_probe  Alias for ai_nas_appliance_experience_acceptance
ai_nas_operator_portal_contract  AI-NAS static operator portal contract for search/report/approval/audit
ai_nas_operator_portal_contract_probe  Alias for ai_nas_operator_portal_contract
ai_nas_production_dependency_bundle  AI-NAS consolidated production dependency evidence bundle
ai_nas_production_dependency_bundle_probe  Alias for ai_nas_production_dependency_bundle
ai_nas_production_blocker_runbook_contract  AI-NAS production blocker remediation runbook contract
ai_nas_production_blocker_runbook_contract_probe  Alias for ai_nas_production_blocker_runbook_contract
ai_nas_evidence_catalog_contract  AI-NAS evidence catalog SQLite provenance contract
ai_nas_evidence_catalog_contract_probe  Alias for ai_nas_evidence_catalog_contract
ai_nas_objective_traceability_contract  AI-NAS objective-to-evidence traceability contract
ai_nas_objective_traceability_contract_probe  Alias for ai_nas_objective_traceability_contract
ai_nas_goal_completion_audit  AI-NAS strict active-goal completion audit for NAS soak, Operator Portal, and Dream7B evidence
ai_nas_goal_completion_audit_probe  Alias for ai_nas_goal_completion_audit
ai_nas_goal_completion_finalizer  AI-NAS post-soak finalizer that waits for watcher gate/runbook and runs the strict goal audit
ai_nas_goal_completion_finalizer_probe  Alias for ai_nas_goal_completion_finalizer
ai_nas_evidence_freshness_contract  AI-NAS production evidence freshness and provenance contract
ai_nas_evidence_freshness_contract_probe  Alias for ai_nas_evidence_freshness_contract
ai_nas_portable_nas_adapter_contract  AI-NAS portable cheap-NAS adapter contract
ai_nas_portable_nas_adapter_contract_probe  Alias for ai_nas_portable_nas_adapter_contract
ai_nas_production_readiness_gate  AI-NAS production readiness gate for appliance claims
ai_nas_production_readiness_gate_probe  Alias for ai_nas_production_readiness_gate
ai_nas_search_evidence_contract  AI-NAS search result evidence contract acceptance
ai_nas_search_evidence_contract_probe  Alias for ai_nas_search_evidence_contract
ai_nas_search_confidence_calibration_contract  AI-NAS search confidence calibration contract
ai_nas_search_confidence_calibration_contract_probe  Alias for ai_nas_search_confidence_calibration_contract
ai_nas_multimodal_intent_routing_contract  AI-NAS multimodal intent routing contract
ai_nas_multimodal_intent_routing_contract_probe  Alias for ai_nas_multimodal_intent_routing_contract
ai_nas_semantic_query_acceptance  AI-NAS MVP semantic fuzzy-query acceptance report
ai_nas_semantic_query_acceptance_probe  Alias for ai_nas_semantic_query_acceptance
ai_nas_action_approval_manifest  AI-NAS MVP dry-run action approval and rollback manifest
ai_nas_action_approval_manifest_probe  Alias for ai_nas_action_approval_manifest
ai_nas_action_manifest_integrity  AI-NAS approval manifest integrity and tamper-refusal contract
ai_nas_action_manifest_integrity_probe  Alias for ai_nas_action_manifest_integrity
ai_nas_operator_approval_inbox  AI-NAS report-only operator approval inbox for action manifests
ai_nas_operator_approval_inbox_probe  Alias for ai_nas_operator_approval_inbox
ai_nas_action_execute_copy  AI-NAS MVP approved copy-only action executor with rollback manifest
ai_nas_action_execute_copy_probe  Alias for ai_nas_action_execute_copy
ai_nas_action_rollback_copy  AI-NAS MVP approved copy-only rollback executor
ai_nas_action_rollback_copy_probe  Alias for ai_nas_action_rollback_copy
ai_nas_destructive_action_governance  AI-NAS destructive action governance contract acceptance
ai_nas_destructive_action_governance_probe  Alias for ai_nas_destructive_action_governance
ai_nas_audit_trail_contract  AI-NAS hash-chained cross-step audit trail contract
ai_nas_audit_trail_contract_probe  Alias for ai_nas_audit_trail_contract
ai_nas_permission_aware_search  AI-NAS MVP permission-aware search with denied-result redaction
ai_nas_permission_aware_search_probe  Alias for ai_nas_permission_aware_search
ai_nas_acl_mapping_readiness  AI-NAS MVP production NAS ACL/user mapping readiness
ai_nas_acl_mapping_readiness_probe  Alias for ai_nas_acl_mapping_readiness
ai_nas_evidence_report  AI-NAS MVP one-click auditable query evidence report
ai_nas_evidence_report_probe  Alias for ai_nas_evidence_report
ai_nas_embedding_search  AI-NAS MVP local lightweight embedding search report
ai_nas_embedding_search_probe  Alias for ai_nas_embedding_search
ai_nas_embedding_backend_readiness  AI-NAS MVP production embedding backend readiness
ai_nas_embedding_backend_readiness_probe  Alias for ai_nas_embedding_backend_readiness
ai_nas_embedding_runtime_contract  AI-NAS production embedding and CLIP runtime contract
ai_nas_embedding_runtime_contract_probe  Alias for ai_nas_embedding_runtime_contract
ai_nas_model_service_resilience  AI-NAS MVP read-only model service crash-recovery preflight
ai_nas_model_service_resilience_probe  Alias for ai_nas_model_service_resilience
ai_nas_model_service_recovery_drill  AI-NAS MVP bounded local model-service recovery drill
ai_nas_model_service_recovery_drill_probe  Alias for ai_nas_model_service_recovery_drill
ai_nas_model_service_recovery_manifest  AI-NAS read-only model-service recovery approval manifest
ai_nas_model_service_recovery_manifest_probe  Alias for ai_nas_model_service_recovery_manifest
ai_nas_model_service_real_recovery_drill  AI-NAS operator-approved real model/OpenClaw service restart drill
ai_nas_model_service_real_recovery_drill_probe  Alias for ai_nas_model_service_real_recovery_drill
ai_nas_ocr_runtime_contract  AI-NAS production OCR runtime contract and smoke report
ai_nas_ocr_runtime_contract_probe  Alias for ai_nas_ocr_runtime_contract
ai_nas_ocr_readiness  AI-NAS MVP OCR runtime readiness and scanned-document gap report
ai_nas_ocr_readiness_probe  Alias for ai_nas_ocr_readiness
ai_nas_ocr_extract  AI-NAS MVP bounded OCR extraction/status report
ai_nas_ocr_extract_probe  Alias for ai_nas_ocr_extract
ai_nas_document_pipeline_acceptance  AI-NAS MVP document pipeline acceptance report
ai_nas_document_pipeline_acceptance_probe  Alias for ai_nas_document_pipeline_acceptance
ai_nas_file_search  AI-NAS MVP fixed natural-language file search demo
ai_nas_file_search_probe  Alias for ai_nas_file_search
ai_nas_folder_rag  AI-NAS MVP folder-scoped evidence-grounded RAG report
ai_nas_folder_rag_probe  Alias for ai_nas_folder_rag
ai_nas_folder_rag_grounding_contract  AI-NAS folder RAG grounding and no-answer contract
ai_nas_folder_rag_grounding_contract_probe  Alias for ai_nas_folder_rag_grounding_contract
ai_nas_folder_summary  AI-NAS MVP fixed Documents folder summary and Q&A demo
ai_nas_folder_summary_probe  Alias for ai_nas_folder_summary
ai_nas_duplicate_report  AI-NAS MVP duplicate file report; no delete or move
ai_nas_duplicate_report_probe  Alias for ai_nas_duplicate_report
ai_nas_photo_similarity  AI-NAS MVP pHash similar photo report; no delete or move
ai_nas_photo_similarity_probe  Alias for ai_nas_photo_similarity
ai_nas_image_embedding_extract  AI-NAS MVP local visual image embedding and CLIP readiness report
ai_nas_image_embedding_extract_probe  Alias for ai_nas_image_embedding_extract
ai_nas_photo_semantic_search  AI-NAS MVP bounded photo semantic search with explicit evidence
ai_nas_photo_semantic_search_probe  Alias for ai_nas_photo_semantic_search
ai_nas_photo_pipeline_acceptance  AI-NAS MVP bounded photo pipeline acceptance report
ai_nas_photo_pipeline_acceptance_probe  Alias for ai_nas_photo_pipeline_acceptance
ai_nas_photo_privacy_governance  AI-NAS photo privacy governance and face-model deferral contract
ai_nas_photo_privacy_governance_probe  Alias for ai_nas_photo_privacy_governance
ai_nas_movie_sort_enhanced  AI-NAS MVP non-destructive movie copy-sort with manifest
ai_nas_movie_sort_enhanced_probe  Alias for ai_nas_movie_sort_enhanced
personal_data_sort_probe  Safe Personal NAS copy-sort with duplicate reporting and source preservation
personal_data_sort_dry_run_probe  Preview Personal NAS organization plan without writing sorted copies
ros2_status_probe      Read-only ROS2/TROS node/topic/service status report
sandbox_status_probe   Read-only Docker/Podman/sandbox capability status report
sandbox_isolation_smoke_probe  Bounded A-006 isolation smoke; no package install and no image pull
security_audit_probe   Read-only OpenClaw/S100P security baseline audit report
service_policy_probe   Read-only service keep/disable/firewall policy plan
service_hardening_plan_probe  Read-only dry-run hardening command plan
service_convergence_decision_probe  Read-only B-010 service convergence decision pack
service_confirmation_template_probe  Read-only B-010 service confirmation template artifact
service_execution_preflight_probe  Read-only B-010 service execution confirmation gate
stability_snapshot_probe  Read-only uptime/resource/log snapshot for A-010
stability_summary_probe  Read-only aggregate summary for A-010 stability snapshots
stability_checkpoint_probe  Read-only A-010 progress projection toward 168h
image_caption_probe  Read-only image metadata caption and JSONL index for B-003
vision_caption_readiness_probe  Read-only local semantic vision caption readiness for B-003
dream7b_readiness_probe  Read-only Dream 7B / local DLM deployment readiness
dream7b_config_template_probe  Read-only B-003 Dream 7B deployment config template artifact
dream7b_smoke_probe  Bounded local Dream 7B smoke test, only when explicit config and local model files exist
home_assistant_config_template_probe  Read-only B-008 Home Assistant env template artifact
home_assistant_status_probe  Read-only Home Assistant API status preflight for B-008
external_input_gate_probe  Read-only B-003/B-008 external input packet gate
control_action_template_probe  Read-only B-009 reviewed action template artifact
control_action_policy_probe  Read-only low-risk control policy and audit preflight for B-009
operator_review_gate_probe  Read-only A-009/B-009/B-010 operator review packet gate
browser_smoke_probe    Headless Chromium local page screenshot smoke test
dataset_card_inventory_probe  Read-only inventory of existing robot DATASET_CARD files
rosbag_snapshot_probe  Bounded ROS bag snapshot for low-risk topics
rosbag_session_probe   Start/status/stop ROS bag self-test for low-risk topics
rosbag_capture_policy_probe  Read-only named ROS bag capture policy and topic classification
rosbag_named_capture_request_probe  Read-only A-009 named capture request template; no recording
rosbag_named_capture_probe  Operator-approved bounded named ROS bag capture
experiment_report_probe  Generate a Markdown summary from workspace reports and datasets
baseline_status_probe  Read-only roll-up status report for the two baseline tracks
baseline_gap_decision_probe  Read-only remaining-gap and next-decision report
baseline_acceptance_probe  Read-only pass/collecting/blocked acceptance gate for all baseline IDs
baseline_acceptance_trend_probe  Read-only trend report across baseline acceptance snapshots
baseline_next_action_queue_probe  Read-only lane-aware next-action queue from current acceptance state
baseline_evidence_manifest_probe  Read-only SHA256 manifest for current baseline evidence files
teacher_baseline_briefing_probe  Read-only teacher-facing briefing package for the two baseline tracks
EOF
    exit 0
    ;;
  openclaw_status_probe)
    shift
    tool_path="$repo_dir/scripts/probes/openclaw_status_probe.sh"
    max_args=1
    ;;
  nas_discovery_probe)
    shift
    tool_path="$repo_dir/scripts/probes/nas_discovery_probe.sh"
    max_args=1
    ;;
  nas_link_blocker_probe)
    shift
    tool_path="$repo_dir/scripts/probes/nas_link_blocker_probe.sh"
    max_args=2
    ;;
  infrastructure_gate_probe)
    shift
    tool_path="$repo_dir/scripts/probes/infrastructure_gate_probe.sh"
    max_args=2
    ;;
  log_diagnose)
    shift
    tool_path="$repo_dir/scripts/probes/log_diagnose.sh"
    max_args=2
    ;;
  index_documents)
    shift
    tool_path="$repo_dir/scripts/probes/index_documents.sh"
    max_args=2
    ;;
  document_daily_summary_probe)
    shift
    tool_path="$repo_dir/scripts/probes/document_daily_summary_probe.sh"
    max_args=2
    ;;
  openclaw_entry_demo_probe)
    shift
    tool_path="$repo_dir/scripts/probes/openclaw_entry_demo_probe.sh"
    max_args=1
    ;;
  ai_nas_movie_sort_demo_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_movie_sort_demo_probe.sh"
    max_args=2
    ;;
  ai_nas_personal_inventory|ai_nas_personal_inventory_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_personal_inventory_probe.sh"
    max_args=0
    ;;
  ai_nas_index_status|ai_nas_index_status_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_index_status_probe.sh"
    max_args=0
    ;;
  ai_nas_index_daemon_readiness|ai_nas_index_daemon_readiness_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_index_daemon_readiness_probe.sh"
    max_args=0
    ;;
  ai_nas_index_daemon_smoke|ai_nas_index_daemon_smoke_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_index_daemon_smoke_probe.sh"
    max_args=0
    ;;
  ai_nas_index_daemon_resident|ai_nas_index_daemon_resident_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_index_daemon_resident_probe.sh"
    max_args=0
    ;;
  ai_nas_index_systemd_daemon_install|ai_nas_index_systemd_daemon_install_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_index_systemd_daemon_install_probe.sh"
    max_args=0
    ;;
  ai_nas_index_rename_detection|ai_nas_index_rename_detection_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_index_rename_detection_probe.sh"
    max_args=0
    ;;
  ai_nas_index_observability_contract|ai_nas_index_observability_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_index_observability_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_sqlite_index_integrity_contract|ai_nas_sqlite_index_integrity_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_sqlite_index_integrity_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_incremental_scan_efficiency_contract|ai_nas_incremental_scan_efficiency_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_incremental_scan_efficiency_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_index_search_isolation_slo|ai_nas_index_search_isolation_slo_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_index_search_isolation_slo_probe.sh"
    max_args=0
    ;;
  ai_nas_perf_benchmark|ai_nas_perf_benchmark_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_perf_benchmark_probe.sh"
    max_args=0
    ;;
  ai_nas_concurrency_stability|ai_nas_concurrency_stability_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_concurrency_stability_probe.sh"
    max_args=0
    ;;
  ai_nas_continuous_task_soak|ai_nas_continuous_task_soak_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_continuous_task_soak_probe.sh"
    max_args=0
    ;;
  ai_nas_nas_backed_long_soak|ai_nas_nas_backed_long_soak_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_nas_backed_long_soak_probe.sh"
    max_args=0
    ;;
  ai_nas_soak_checkpoint_resume|ai_nas_soak_checkpoint_resume_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_soak_checkpoint_resume_probe.sh"
    max_args=0
    ;;
  ai_nas_queue_backpressure_slo|ai_nas_queue_backpressure_slo_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_queue_backpressure_slo_probe.sh"
    max_args=0
    ;;
  ai_nas_user_facing_tail_latency|ai_nas_user_facing_tail_latency_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_user_facing_tail_latency_probe.sh"
    max_args=0
    ;;
  ai_nas_bpu_headroom_slo|ai_nas_bpu_headroom_slo_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_bpu_headroom_slo_probe.sh"
    max_args=0
    ;;
  ai_nas_operational_slo_rollup_contract|ai_nas_operational_slo_rollup_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_operational_slo_rollup_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_allowlist_governance_audit|ai_nas_allowlist_governance_audit_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_allowlist_governance_audit_probe.sh"
    max_args=0
    ;;
  ai_nas_task_queue|ai_nas_task_queue_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_task_queue_probe.sh"
    max_args=0
    ;;
  ai_nas_case_packet|ai_nas_case_packet_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_case_packet_probe.sh"
    max_args=1
    ;;
  ai_nas_appliance_experience_acceptance|ai_nas_appliance_experience_acceptance_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_appliance_experience_acceptance_probe.sh"
    max_args=0
    ;;
  ai_nas_operator_portal_contract|ai_nas_operator_portal_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_operator_portal_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_production_dependency_bundle|ai_nas_production_dependency_bundle_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_production_dependency_bundle_probe.sh"
    max_args=0
    ;;
  ai_nas_production_blocker_runbook_contract|ai_nas_production_blocker_runbook_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_production_blocker_runbook_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_evidence_catalog_contract|ai_nas_evidence_catalog_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_evidence_catalog_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_objective_traceability_contract|ai_nas_objective_traceability_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_objective_traceability_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_goal_completion_audit|ai_nas_goal_completion_audit_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_goal_completion_audit_probe.sh"
    max_args=0
    ;;
  ai_nas_goal_completion_finalizer|ai_nas_goal_completion_finalizer_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_goal_completion_finalizer_probe.sh"
    max_args=1
    ;;
  ai_nas_evidence_freshness_contract|ai_nas_evidence_freshness_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_evidence_freshness_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_portable_nas_adapter_contract|ai_nas_portable_nas_adapter_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_portable_nas_adapter_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_production_readiness_gate|ai_nas_production_readiness_gate_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_production_readiness_gate_probe.sh"
    max_args=0
    ;;
  ai_nas_search_evidence_contract|ai_nas_search_evidence_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_search_evidence_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_search_confidence_calibration_contract|ai_nas_search_confidence_calibration_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_search_confidence_calibration_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_multimodal_intent_routing_contract|ai_nas_multimodal_intent_routing_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_multimodal_intent_routing_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_semantic_query_acceptance|ai_nas_semantic_query_acceptance_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_semantic_query_acceptance_probe.sh"
    max_args=0
    ;;
  ai_nas_action_approval_manifest|ai_nas_action_approval_manifest_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_action_approval_manifest_probe.sh"
    max_args=1
    ;;
  ai_nas_action_manifest_integrity|ai_nas_action_manifest_integrity_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_action_manifest_integrity_probe.sh"
    max_args=0
    ;;
  ai_nas_operator_approval_inbox|ai_nas_operator_approval_inbox_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_operator_approval_inbox_probe.sh"
    max_args=0
    ;;
  ai_nas_action_execute_copy|ai_nas_action_execute_copy_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_action_execute_copy_probe.sh"
    max_args=2
    ;;
  ai_nas_action_rollback_copy|ai_nas_action_rollback_copy_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_action_rollback_copy_probe.sh"
    max_args=2
    ;;
  ai_nas_destructive_action_governance|ai_nas_destructive_action_governance_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_destructive_action_governance_probe.sh"
    max_args=0
    ;;
  ai_nas_audit_trail_contract|ai_nas_audit_trail_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_audit_trail_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_permission_aware_search|ai_nas_permission_aware_search_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_permission_aware_search_probe.sh"
    max_args=2
    ;;
  ai_nas_acl_mapping_readiness|ai_nas_acl_mapping_readiness_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_acl_mapping_readiness_probe.sh"
    max_args=0
    ;;
  ai_nas_evidence_report|ai_nas_evidence_report_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_evidence_report_probe.sh"
    max_args=1
    ;;
  ai_nas_embedding_search|ai_nas_embedding_search_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_embedding_search_probe.sh"
    max_args=1
    ;;
  ai_nas_embedding_backend_readiness|ai_nas_embedding_backend_readiness_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_embedding_backend_readiness_probe.sh"
    max_args=0
    ;;
  ai_nas_embedding_runtime_contract|ai_nas_embedding_runtime_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_embedding_runtime_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_model_service_resilience|ai_nas_model_service_resilience_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_model_service_resilience_probe.sh"
    max_args=0
    ;;
  ai_nas_model_service_recovery_drill|ai_nas_model_service_recovery_drill_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_model_service_recovery_drill_probe.sh"
    max_args=0
    ;;
  ai_nas_model_service_recovery_manifest|ai_nas_model_service_recovery_manifest_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_model_service_recovery_manifest_probe.sh"
    max_args=0
    ;;
  ai_nas_model_service_real_recovery_drill|ai_nas_model_service_real_recovery_drill_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_model_service_real_recovery_drill_probe.sh"
    max_args=3
    ;;
  ai_nas_ocr_runtime_contract|ai_nas_ocr_runtime_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_ocr_runtime_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_ocr_readiness|ai_nas_ocr_readiness_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_ocr_readiness_probe.sh"
    max_args=0
    ;;
  ai_nas_ocr_extract|ai_nas_ocr_extract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_ocr_extract_probe.sh"
    max_args=0
    ;;
  ai_nas_document_pipeline_acceptance|ai_nas_document_pipeline_acceptance_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_document_pipeline_acceptance_probe.sh"
    max_args=0
    ;;
  ai_nas_file_search|ai_nas_file_search_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_file_search_probe.sh"
    max_args=1
    ;;
  ai_nas_folder_rag|ai_nas_folder_rag_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_folder_rag_probe.sh"
    max_args=2
    ;;
  ai_nas_folder_rag_grounding_contract|ai_nas_folder_rag_grounding_contract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_folder_rag_grounding_contract_probe.sh"
    max_args=0
    ;;
  ai_nas_folder_summary|ai_nas_folder_summary_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_folder_summary_probe.sh"
    max_args=0
    ;;
  ai_nas_duplicate_report|ai_nas_duplicate_report_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_duplicate_report_probe.sh"
    max_args=0
    ;;
  ai_nas_photo_similarity|ai_nas_photo_similarity_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_photo_similarity_probe.sh"
    max_args=0
    ;;
  ai_nas_image_embedding_extract|ai_nas_image_embedding_extract_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_image_embedding_extract_probe.sh"
    max_args=0
    ;;
  ai_nas_photo_semantic_search|ai_nas_photo_semantic_search_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_photo_semantic_search_probe.sh"
    max_args=1
    ;;
  ai_nas_photo_pipeline_acceptance|ai_nas_photo_pipeline_acceptance_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_photo_pipeline_acceptance_probe.sh"
    max_args=0
    ;;
  ai_nas_photo_privacy_governance|ai_nas_photo_privacy_governance_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_photo_privacy_governance_probe.sh"
    max_args=0
    ;;
  ai_nas_movie_sort_enhanced|ai_nas_movie_sort_enhanced_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ai_nas_movie_sort_enhanced_probe.sh"
    max_args=0
    ;;
  personal_data_sort_probe)
    shift
    tool_path="$repo_dir/scripts/probes/personal_data_sort_probe.sh"
    max_args=4
    ;;
  personal_data_sort_dry_run_probe)
    shift
    tool_path="$repo_dir/scripts/probes/personal_data_sort_dry_run_probe.sh"
    max_args=4
    ;;
  ros2_status_probe)
    shift
    tool_path="$repo_dir/scripts/probes/ros2_status_probe.sh"
    max_args=1
    ;;
  sandbox_status_probe)
    shift
    tool_path="$repo_dir/scripts/probes/sandbox_status_probe.sh"
    max_args=1
    ;;
  sandbox_isolation_smoke_probe)
    shift
    tool_path="$repo_dir/scripts/probes/sandbox_isolation_smoke_probe.sh"
    max_args=1
    ;;
  security_audit_probe)
    shift
    tool_path="$repo_dir/scripts/probes/security_audit_probe.sh"
    max_args=1
    ;;
  service_policy_probe)
    shift
    tool_path="$repo_dir/scripts/probes/service_policy_probe.sh"
    max_args=1
    ;;
  service_hardening_plan_probe)
    shift
    tool_path="$repo_dir/scripts/probes/service_hardening_plan_probe.sh"
    max_args=1
    ;;
  service_convergence_decision_probe)
    shift
    tool_path="$repo_dir/scripts/probes/service_convergence_decision_probe.sh"
    max_args=2
    ;;
  service_confirmation_template_probe)
    shift
    tool_path="$repo_dir/scripts/probes/service_confirmation_template_probe.sh"
    max_args=1
    ;;
  service_execution_preflight_probe)
    shift
    tool_path="$repo_dir/scripts/probes/service_execution_preflight_probe.sh"
    max_args=2
    ;;
  stability_snapshot_probe)
    shift
    tool_path="$repo_dir/scripts/probes/stability_snapshot_probe.sh"
    max_args=1
    ;;
  stability_summary_probe)
    shift
    tool_path="$repo_dir/scripts/probes/stability_summary_probe.sh"
    max_args=2
    ;;
  stability_checkpoint_probe)
    shift
    tool_path="$repo_dir/scripts/probes/stability_checkpoint_probe.sh"
    max_args=4
    ;;
  image_caption_probe)
    shift
    tool_path="$repo_dir/scripts/probes/image_caption_probe.sh"
    max_args=2
    ;;
  vision_caption_readiness_probe)
    shift
    tool_path="$repo_dir/scripts/probes/vision_caption_readiness_probe.sh"
    max_args=2
    ;;
  dream7b_readiness_probe)
    shift
    tool_path="$repo_dir/scripts/probes/dream7b_readiness_probe.sh"
    max_args=1
    ;;
  dream7b_config_template_probe)
    shift
    tool_path="$repo_dir/scripts/probes/dream7b_config_template_probe.sh"
    max_args=1
    ;;
  dream7b_smoke_probe)
    shift
    tool_path="$repo_dir/scripts/probes/dream7b_smoke_probe.sh"
    max_args=2
    ;;
  home_assistant_config_template_probe)
    shift
    tool_path="$repo_dir/scripts/probes/home_assistant_config_template_probe.sh"
    max_args=1
    ;;
  home_assistant_status_probe)
    shift
    tool_path="$repo_dir/scripts/probes/home_assistant_status_probe.sh"
    max_args=1
    ;;
  external_input_gate_probe)
    shift
    tool_path="$repo_dir/scripts/probes/external_input_gate_probe.sh"
    max_args=2
    ;;
  control_action_template_probe)
    shift
    tool_path="$repo_dir/scripts/probes/control_action_template_probe.sh"
    max_args=1
    ;;
  control_action_policy_probe)
    shift
    tool_path="$repo_dir/scripts/probes/control_action_policy_probe.sh"
    max_args=1
    ;;
  operator_review_gate_probe)
    shift
    tool_path="$repo_dir/scripts/probes/operator_review_gate_probe.sh"
    max_args=2
    ;;
  browser_smoke_probe)
    shift
    tool_path="$repo_dir/scripts/probes/browser_smoke_probe.sh"
    max_args=1
    ;;
  dataset_card_inventory_probe)
    shift
    tool_path="$repo_dir/scripts/probes/dataset_card_inventory_probe.sh"
    max_args=2
    ;;
  rosbag_snapshot_probe)
    shift
    tool_path="$repo_dir/scripts/probes/rosbag_snapshot_probe.sh"
    max_args=2
    ;;
  rosbag_session_probe)
    shift
    tool_path="$repo_dir/scripts/probes/rosbag_session_probe.sh"
    max_args=2
    ;;
  rosbag_capture_policy_probe)
    shift
    tool_path="$repo_dir/scripts/probes/rosbag_capture_policy_probe.sh"
    max_args=1
    ;;
  rosbag_named_capture_request_probe)
    shift
    tool_path="$repo_dir/scripts/probes/rosbag_named_capture_request_probe.sh"
    max_args=1
    ;;
  rosbag_named_capture_probe)
    shift
    tool_path="$repo_dir/scripts/probes/rosbag_named_capture_probe.sh"
    max_args=2
    ;;
  experiment_report_probe)
    shift
    tool_path="$repo_dir/scripts/probes/experiment_report_probe.sh"
    max_args=1
    ;;
  baseline_status_probe)
    shift
    tool_path="$repo_dir/scripts/probes/baseline_status_probe.sh"
    max_args=2
    ;;
  baseline_gap_decision_probe)
    shift
    tool_path="$repo_dir/scripts/probes/baseline_gap_decision_probe.sh"
    max_args=2
    ;;
  baseline_acceptance_probe)
    shift
    tool_path="$repo_dir/scripts/probes/baseline_acceptance_probe.sh"
    max_args=2
    ;;
  baseline_acceptance_trend_probe)
    shift
    tool_path="$repo_dir/scripts/probes/baseline_acceptance_trend_probe.sh"
    max_args=2
    ;;
  baseline_next_action_queue_probe)
    shift
    tool_path="$repo_dir/scripts/probes/baseline_next_action_queue_probe.sh"
    max_args=3
    ;;
  baseline_evidence_manifest_probe)
    shift
    tool_path="$repo_dir/scripts/probes/baseline_evidence_manifest_probe.sh"
    max_args=2
    ;;
  teacher_baseline_briefing_probe)
    shift
    tool_path="$repo_dir/scripts/probes/teacher_baseline_briefing_probe.sh"
    max_args=2
    ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    echo "Tool is not allowlisted: $tool_id" >&2
    exit 3
    ;;
esac

if [[ ! -f "$tool_path" ]]; then
  echo "Allowlisted tool is missing: $tool_path" >&2
  exit 4
fi

if [[ $# -gt "$max_args" ]]; then
  echo "Too many arguments for $tool_id" >&2
  exit 2
fi

if [[ "$tool_id" == "ai_nas_action_execute_copy" || "$tool_id" == "ai_nas_action_execute_copy_probe" ]]; then
  if [[ $# -ne 2 ]]; then
    echo "ai_nas_action_execute_copy requires manifest path and exact approval phrase" >&2
    exit 2
  fi
  case "${1:-}" in
    /tmp/*|/mnt/nas/openclaw/reports/ai_nas_mvp/*|/root/.openclaw/workspace/reports/ai_nas_mvp/*) ;;
    *)
      echo "Refusing manifest path outside approved AI-NAS report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    APPROVE\ apm-*) ;;
    *)
      echo "Refusing malformed approval phrase" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "ai_nas_action_rollback_copy" || "$tool_id" == "ai_nas_action_rollback_copy_probe" ]]; then
  if [[ $# -ne 2 ]]; then
    echo "ai_nas_action_rollback_copy requires rollback manifest path and exact rollback phrase" >&2
    exit 2
  fi
  case "${1:-}" in
    /tmp/*|/mnt/nas/openclaw/reports/ai_nas_mvp/*|/root/.openclaw/workspace/reports/ai_nas_mvp/*) ;;
    *)
      echo "Refusing rollback manifest path outside approved AI-NAS report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ROLLBACK\ apm-*) ;;
    *)
      echo "Refusing malformed rollback phrase" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "openclaw_status_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "nas_discovery_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "infrastructure_gate_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/root/.openclaw/workspace|/root/.openclaw/workspace/*) ;;
    *)
      echo "Refusing workspace outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing report path outside approved baseline report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "ros2_status_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "sandbox_status_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "sandbox_isolation_smoke_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "security_audit_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "service_policy_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "service_hardening_plan_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "service_convergence_decision_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing input path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "service_confirmation_template_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "service_execution_preflight_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/root/.openclaw/workspace/config/service_convergence_confirmations.json|/mnt/nas/openclaw/config/service_convergence_confirmations.json|/tmp/service_convergence_confirmations.json) ;;
    *)
      echo "Refusing confirmation config outside approved paths: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "stability_snapshot_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "stability_summary_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing input path outside approved stability snapshot directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "stability_checkpoint_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing input path outside approved stability snapshot directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing report directory outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
  case "${3:-}" in
    ""|[0-9]|[1-9][0-9]|[1-9][0-9][0-9]|[1-9][0-9][0-9][0-9]) ;;
    *)
      echo "Refusing non-integer target hours: ${3:-}" >&2
      exit 2
      ;;
  esac
  case "${4:-}" in
    ""|[0-9]|[1-9][0-9]|[0-9].[0-9]*|[1-9][0-9].[0-9]*|[1-9][0-9][0-9].[0-9]*) ;;
    *)
      echo "Refusing non-numeric max gap hours: ${4:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "image_caption_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/photos|/mnt/nas/openclaw/photos/*|/root/.openclaw/workspace/photos|/root/.openclaw/workspace/photos/*) ;;
    *)
      echo "Refusing input path outside approved photo directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "vision_caption_readiness_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/photos|/mnt/nas/openclaw/photos/*|/root/.openclaw/workspace/photos|/root/.openclaw/workspace/photos/*) ;;
    *)
      echo "Refusing input path outside approved photo directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "dream7b_readiness_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "dream7b_smoke_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/root/.openclaw/workspace/config/dream7b_deployment.json|/mnt/nas/openclaw/config/dream7b_deployment.json|/mnt/nas/openclaw/models/dream7b/dream7b_deployment.json|/tmp/dream7b_deployment.json) ;;
    *)
      echo "Refusing Dream 7B config outside approved paths: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "home_assistant_config_template_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "home_assistant_status_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "external_input_gate_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing workspace outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing report directory outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "control_action_template_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "control_action_policy_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "operator_review_gate_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing workspace outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing report directory outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "browser_smoke_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "dataset_card_inventory_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/robot_datasets|/mnt/nas/openclaw/robot_datasets/*|/root/.openclaw/workspace/robot_datasets|/root/.openclaw/workspace/robot_datasets/*) ;;
    *)
      echo "Refusing dataset root outside approved robot dataset directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing report directory outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "rosbag_snapshot_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/robot_datasets|/mnt/nas/openclaw/robot_datasets/*|/root/.openclaw/workspace/robot_datasets|/root/.openclaw/workspace/robot_datasets/*) ;;
    *)
      echo "Refusing dataset path outside approved robot dataset directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing report path outside approved probe directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "rosbag_session_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/robot_datasets|/mnt/nas/openclaw/robot_datasets/*|/root/.openclaw/workspace/robot_datasets|/root/.openclaw/workspace/robot_datasets/*) ;;
    *)
      echo "Refusing dataset path outside approved robot dataset directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing report path outside approved probe directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "rosbag_capture_policy_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "rosbag_named_capture_request_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "rosbag_named_capture_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/robot_datasets|/mnt/nas/openclaw/robot_datasets/*|/root/.openclaw/workspace/robot_datasets|/root/.openclaw/workspace/robot_datasets/*) ;;
    *)
      echo "Refusing dataset path outside approved robot dataset directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing report path outside approved probe directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "experiment_report_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "log_diagnose" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/*|/root/.openclaw/workspace/logs|/root/.openclaw/workspace/logs/*) ;;
    *)
      echo "Refusing log path outside approved directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "index_documents" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/documents|/mnt/nas/openclaw/documents/*|/root/.openclaw/workspace/documents|/root/.openclaw/workspace/documents/*) ;;
    *)
      echo "Refusing input path outside approved document directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "baseline_status_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*) ;;
    *)
      echo "Refusing workspace outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "baseline_gap_decision_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing NAS/workspace root outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "baseline_acceptance_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing NAS/workspace root outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "baseline_acceptance_trend_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing NAS/workspace root outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "baseline_next_action_queue_probe" ]]; then
  audit_decision_arg="${3:-}"
  audit_decision_arg="${audit_decision_arg%$'\r'}"
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing workspace outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
  case "$audit_decision_arg" in
    ""|continue|continue-non-nas-readonly-only|continue-nas-backed-baseline|hold-blocked-items) ;;
    *)
      echo "Refusing unknown audit decision: ${3:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "baseline_evidence_manifest_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing NAS/workspace root outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "teacher_baseline_briefing_probe" ]]; then
  case "${1:-}" in
    ""|/root/.openclaw/workspace|/root/.openclaw/workspace/*|/mnt/nas/openclaw|/mnt/nas/openclaw/*|/tmp/*) ;;
    *)
      echo "Refusing NAS/workspace root outside approved baseline directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "document_daily_summary_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/documents|/mnt/nas/openclaw/documents/*|/root/.openclaw/workspace/documents|/root/.openclaw/workspace/documents/*) ;;
    *)
      echo "Refusing input path outside approved document directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "openclaw_entry_demo_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing report directory outside approved demo report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "ai_nas_movie_sort_demo_probe" ]]; then
  case "${1:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/demo/ai-nas-movie-sort|/mnt/nas/openclaw/demo/ai-nas-movie-sort/*|/root/.openclaw/workspace/demo/ai-nas-movie-sort|/root/.openclaw/workspace/demo/ai-nas-movie-sort/*) ;;
    *)
      echo "Refusing demo root outside approved AI NAS movie-sort demo directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing report directory outside approved demo report directories: ${2:-}" >&2
      exit 2
      ;;
  esac
fi

if [[ "$tool_id" == "ai_nas_model_service_real_recovery_drill" || "$tool_id" == "ai_nas_model_service_real_recovery_drill_probe" ]]; then
  if [[ -z "${1:-}" ]]; then
    echo "manifest_json is required for real service recovery drill." >&2
    exit 2
  fi
  case "${1:-}" in
    /tmp/*|/mnt/nas/openclaw/reports/ai_nas_mvp/*|/root/.openclaw/workspace/reports/ai_nas_mvp/*) ;;
    *)
      echo "Refusing recovery manifest outside approved AI-NAS report directories: ${1:-}" >&2
      exit 2
      ;;
  esac
  if [[ -n "${2:-}" && ! "${2:-}" =~ ^APPROVE-RECOVERY\ msr-[a-f0-9]{16}$ ]]; then
    echo "approval_phrase must match APPROVE-RECOVERY msr-<16 hex chars>." >&2
    exit 2
  fi
  if [[ -n "${3:-}" && "${3:-}" != "--execute" ]]; then
    echo "third argument must be --execute when present." >&2
    exit 2
  fi
  if [[ "${3:-}" == "--execute" && -z "${2:-}" ]]; then
    echo "approval_phrase is required when --execute is present." >&2
    exit 2
  fi
fi

if [[ "$tool_id" == "personal_data_sort_probe" ]]; then
  case "${1:-}" in
    ""|Personal) ;;
    *)
      echo "Refusing SMB share outside approved Personal share: ${1:-}" >&2
      exit 2
      ;;
  esac
  case "${2:-}" in
    ""|/|Movies|Movies/*|Documents|Documents/*|Photos|Photos/*|Datasets|Datasets/*|Inbox|Inbox/*) ;;
    *)
      echo "Refusing source root outside approved Personal subtrees: ${2:-}" >&2
      exit 2
      ;;
  esac
  case "${3:-}" in
    ""|Sorted|Sorted/*) ;;
    *)
      echo "Refusing sorted root outside Personal/Sorted: ${3:-}" >&2
      exit 2
      ;;
  esac
  case "${4:-}" in
    ""|/tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing report directory outside approved report directories: ${4:-}" >&2
      exit 2
      ;;
  esac
fi

exec bash "$tool_path" "$@"
