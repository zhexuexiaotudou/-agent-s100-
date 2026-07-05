#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tool_id="${1:-}"
shift || true

usage() {
  cat <<'EOF'
Usage:
  ai_nas_allowlisted_tool.sh ai_nas_personal_inventory [--bootstrap-demo]
  ai_nas_allowlisted_tool.sh ai_nas_controlled_personal_seed [--execute]
  ai_nas_allowlisted_tool.sh ai_nas_index_status
  ai_nas_allowlisted_tool.sh ai_nas_index_daemon_readiness
  ai_nas_allowlisted_tool.sh ai_nas_index_daemon_smoke
  ai_nas_allowlisted_tool.sh ai_nas_index_daemon_resident
  ai_nas_allowlisted_tool.sh ai_nas_index_systemd_daemon_install
  ai_nas_allowlisted_tool.sh ai_nas_index_rename_detection
  ai_nas_allowlisted_tool.sh ai_nas_index_observability_contract
  ai_nas_allowlisted_tool.sh ai_nas_sqlite_index_integrity_contract
  ai_nas_allowlisted_tool.sh ai_nas_incremental_scan_efficiency_contract
  ai_nas_allowlisted_tool.sh ai_nas_index_search_isolation_slo
  ai_nas_allowlisted_tool.sh ai_nas_perf_benchmark
  ai_nas_allowlisted_tool.sh ai_nas_concurrency_stability
  ai_nas_allowlisted_tool.sh ai_nas_continuous_task_soak
  ai_nas_allowlisted_tool.sh ai_nas_nas_backed_long_soak
  ai_nas_allowlisted_tool.sh ai_nas_soak_completion_gate_watcher --pid-file /mnt/nas/openclaw/reports/ai_nas_mvp/long_soak_jobs/...
  ai_nas_allowlisted_tool.sh ai_nas_soak_checkpoint_resume
  ai_nas_allowlisted_tool.sh ai_nas_queue_backpressure_slo
  ai_nas_allowlisted_tool.sh ai_nas_user_facing_tail_latency
  ai_nas_allowlisted_tool.sh ai_nas_bpu_headroom_slo
  ai_nas_allowlisted_tool.sh ai_nas_operational_slo_rollup_contract
  ai_nas_allowlisted_tool.sh ai_nas_edge_cloud_router
  ai_nas_allowlisted_tool.sh dream7b_perf_identity
  ai_nas_allowlisted_tool.sh ai_nas_allowlist_governance_audit
  ai_nas_allowlisted_tool.sh ai_nas_task_queue
  ai_nas_allowlisted_tool.sh ai_nas_case_packet "query"
  ai_nas_allowlisted_tool.sh ai_nas_appliance_experience_acceptance
  ai_nas_allowlisted_tool.sh ai_nas_operator_portal_contract
  ai_nas_allowlisted_tool.sh ai_nas_operator_portal_server [--port 8765]
  ai_nas_allowlisted_tool.sh ai_nas_production_dependency_bundle
  ai_nas_allowlisted_tool.sh ai_nas_production_blocker_runbook_contract
  ai_nas_allowlisted_tool.sh ai_nas_evidence_catalog_contract
  ai_nas_allowlisted_tool.sh ai_nas_objective_traceability_contract
  ai_nas_allowlisted_tool.sh ai_nas_goal_completion_audit
  ai_nas_allowlisted_tool.sh ai_nas_goal_completion_finalizer
  ai_nas_allowlisted_tool.sh ai_nas_evidence_freshness_contract
  ai_nas_allowlisted_tool.sh ai_nas_portable_nas_adapter_contract
  ai_nas_allowlisted_tool.sh ai_nas_production_readiness_gate
  ai_nas_allowlisted_tool.sh ai_nas_official_ppocr_wrapper
  ai_nas_allowlisted_tool.sh ai_nas_official_route_readiness_gate
  ai_nas_allowlisted_tool.sh ai_nas_product_closure_gate
  ai_nas_allowlisted_tool.sh ai_nas_search_evidence_contract
  ai_nas_allowlisted_tool.sh ai_nas_search_confidence_calibration_contract
  ai_nas_allowlisted_tool.sh ai_nas_multimodal_intent_routing_contract
  ai_nas_allowlisted_tool.sh ai_nas_semantic_query_acceptance
  ai_nas_allowlisted_tool.sh ai_nas_action_approval_manifest "query"
  ai_nas_allowlisted_tool.sh ai_nas_action_manifest_integrity
  ai_nas_allowlisted_tool.sh ai_nas_operator_approval_inbox
  ai_nas_allowlisted_tool.sh ai_nas_action_execute_copy manifest.json "APPROVE manifest-id"
  ai_nas_allowlisted_tool.sh ai_nas_action_rollback_copy rollback_manifest.json "ROLLBACK manifest-id"
  ai_nas_allowlisted_tool.sh ai_nas_destructive_action_governance
  ai_nas_allowlisted_tool.sh ai_nas_audit_trail_contract
  ai_nas_allowlisted_tool.sh ai_nas_permission_aware_search "query" [principal]
  ai_nas_allowlisted_tool.sh ai_nas_acl_mapping_readiness
  ai_nas_allowlisted_tool.sh ai_nas_evidence_report "query"
  ai_nas_allowlisted_tool.sh ai_nas_embedding_search "query"
  ai_nas_allowlisted_tool.sh ai_nas_embedding_backend_readiness
  ai_nas_allowlisted_tool.sh ai_nas_embedding_runtime_contract
  ai_nas_allowlisted_tool.sh ai_nas_model_service_resilience
  ai_nas_allowlisted_tool.sh ai_nas_model_service_recovery_drill
  ai_nas_allowlisted_tool.sh ai_nas_model_service_recovery_manifest
  ai_nas_allowlisted_tool.sh ai_nas_model_service_real_recovery_drill --manifest-json manifest.json --approval-phrase "APPROVE-RECOVERY manifest-id" --execute
  ai_nas_allowlisted_tool.sh ai_nas_ocr_runtime_contract
  ai_nas_allowlisted_tool.sh ai_nas_ocr_readiness
  ai_nas_allowlisted_tool.sh ai_nas_ocr_extract
  ai_nas_allowlisted_tool.sh ai_nas_document_pipeline_acceptance
  ai_nas_allowlisted_tool.sh ai_nas_file_search "query"
  ai_nas_allowlisted_tool.sh ai_nas_folder_rag [folder] [question]
  ai_nas_allowlisted_tool.sh ai_nas_folder_rag_grounding_contract
  ai_nas_allowlisted_tool.sh ai_nas_folder_summary [folder] [question]
  ai_nas_allowlisted_tool.sh ai_nas_duplicate_report
  ai_nas_allowlisted_tool.sh ai_nas_photo_similarity
  ai_nas_allowlisted_tool.sh ai_nas_image_embedding_extract
  ai_nas_allowlisted_tool.sh ai_nas_photo_semantic_search "query"
  ai_nas_allowlisted_tool.sh ai_nas_photo_pipeline_acceptance
  ai_nas_allowlisted_tool.sh ai_nas_photo_privacy_governance
  ai_nas_allowlisted_tool.sh ai_nas_movie_sort_enhanced [--copy]

Environment:
  AI_NAS_PERSONAL_ROOT=/mnt/nas/openclaw/Personal
  AI_NAS_REPORT_ROOT=/mnt/nas/openclaw/reports/ai_nas_mvp

Only fixed probe IDs are accepted. This dispatcher never evaluates arbitrary
commands or script paths.
EOF
}

case "$tool_id" in
  ai_nas_personal_inventory)
    exec python3 "$script_dir/ai_nas_personal_inventory_probe.py" "$@"
    ;;
  ai_nas_controlled_personal_seed)
    exec python3 "$script_dir/ai_nas_controlled_personal_seed_probe.py" "$@"
    ;;
  ai_nas_index_status)
    exec python3 "$script_dir/ai_nas_index_status_probe.py" "$@"
    ;;
  ai_nas_index_daemon_readiness)
    exec python3 "$script_dir/ai_nas_index_daemon_readiness_probe.py" "$@"
    ;;
  ai_nas_index_daemon_smoke)
    exec python3 "$script_dir/ai_nas_index_daemon_smoke_probe.py" "$@"
    ;;
  ai_nas_index_daemon_resident)
    exec python3 "$script_dir/ai_nas_index_daemon_resident_probe.py" "$@"
    ;;
  ai_nas_index_systemd_daemon_install)
    exec python3 "$script_dir/ai_nas_index_systemd_daemon_install_probe.py" "$@"
    ;;
  ai_nas_index_rename_detection)
    exec python3 "$script_dir/ai_nas_index_rename_detection_probe.py" "$@"
    ;;
  ai_nas_index_observability_contract)
    exec python3 "$script_dir/ai_nas_index_observability_contract_probe.py" "$@"
    ;;
  ai_nas_sqlite_index_integrity_contract)
    exec python3 "$script_dir/ai_nas_index_integrity_contract_probe.py" "$@"
    ;;
  ai_nas_incremental_scan_efficiency_contract)
    exec python3 "$script_dir/ai_nas_incremental_scan_efficiency_contract_probe.py" "$@"
    ;;
  ai_nas_index_search_isolation_slo)
    exec python3 "$script_dir/ai_nas_index_search_isolation_slo_probe.py" "$@"
    ;;
  ai_nas_perf_benchmark)
    exec python3 "$script_dir/ai_nas_perf_benchmark_probe.py" "$@"
    ;;
  ai_nas_concurrency_stability)
    exec python3 "$script_dir/ai_nas_concurrency_stability_probe.py" "$@"
    ;;
  ai_nas_continuous_task_soak)
    exec python3 "$script_dir/ai_nas_continuous_task_soak_probe.py" "$@"
    ;;
  ai_nas_nas_backed_long_soak)
    exec python3 "$script_dir/ai_nas_nas_backed_long_soak_probe.py" "$@"
    ;;
  ai_nas_soak_completion_gate_watcher)
    exec python3 "$script_dir/ai_nas_soak_completion_gate_watcher_probe.py" "$@"
    ;;
  ai_nas_soak_checkpoint_resume)
    exec python3 "$script_dir/ai_nas_soak_checkpoint_resume_probe.py" "$@"
    ;;
  ai_nas_queue_backpressure_slo)
    exec python3 "$script_dir/ai_nas_queue_backpressure_slo_probe.py" "$@"
    ;;
  ai_nas_user_facing_tail_latency)
    exec python3 "$script_dir/ai_nas_user_facing_tail_latency_probe.py" "$@"
    ;;
  ai_nas_bpu_headroom_slo)
    exec python3 "$script_dir/ai_nas_bpu_headroom_slo_probe.py" "$@"
    ;;
  ai_nas_operational_slo_rollup_contract)
    exec python3 "$script_dir/ai_nas_operational_slo_rollup_contract_probe.py" "$@"
    ;;
  ai_nas_edge_cloud_router)
    exec python3 "$script_dir/ai_nas_edge_cloud_router_probe.py" "$@"
    ;;
  dream7b_perf_identity)
    exec python3 "$script_dir/dream7b_perf_identity_probe.py" "$@"
    ;;
  ai_nas_allowlist_governance_audit)
    exec python3 "$script_dir/ai_nas_allowlist_governance_audit_probe.py" "$@"
    ;;
  ai_nas_task_queue)
    exec python3 "$script_dir/ai_nas_task_queue_probe.py" "$@"
    ;;
  ai_nas_case_packet)
    exec python3 "$script_dir/ai_nas_case_packet_probe.py" "$@"
    ;;
  ai_nas_appliance_experience_acceptance)
    exec python3 "$script_dir/ai_nas_appliance_experience_acceptance_probe.py" "$@"
    ;;
  ai_nas_operator_portal_contract)
    exec python3 "$script_dir/ai_nas_operator_portal_contract_probe.py" "$@"
    ;;
  ai_nas_operator_portal_server)
    exec python3 "$script_dir/ai_nas_operator_portal_server.py" "$@"
    ;;
  ai_nas_production_dependency_bundle)
    exec python3 "$script_dir/ai_nas_production_dependency_bundle_probe.py" "$@"
    ;;
  ai_nas_production_blocker_runbook_contract)
    exec python3 "$script_dir/ai_nas_production_blocker_runbook_contract_probe.py" "$@"
    ;;
  ai_nas_evidence_catalog_contract)
    exec python3 "$script_dir/ai_nas_evidence_catalog_contract_probe.py" "$@"
    ;;
  ai_nas_objective_traceability_contract)
    exec python3 "$script_dir/ai_nas_objective_traceability_contract_probe.py" "$@"
    ;;
  ai_nas_goal_completion_audit)
    exec python3 "$script_dir/ai_nas_goal_completion_audit_probe.py" "$@"
    ;;
  ai_nas_goal_completion_finalizer)
    exec python3 "$script_dir/ai_nas_goal_completion_finalizer_probe.py" "$@"
    ;;
  ai_nas_evidence_freshness_contract)
    exec python3 "$script_dir/ai_nas_evidence_freshness_contract_probe.py" "$@"
    ;;
  ai_nas_portable_nas_adapter_contract)
    exec python3 "$script_dir/ai_nas_portable_nas_adapter_contract_probe.py" "$@"
    ;;
  ai_nas_production_readiness_gate)
    exec python3 "$script_dir/ai_nas_production_readiness_gate_probe.py" "$@"
    ;;
  ai_nas_official_ppocr_wrapper)
    exec python3 "$script_dir/ai_nas_official_ppocr_wrapper_probe.py" "$@"
    ;;
  ai_nas_official_route_readiness_gate)
    exec python3 "$script_dir/ai_nas_official_route_readiness_gate_probe.py" "$@"
    ;;
  ai_nas_product_closure_gate)
    exec python3 "$script_dir/ai_nas_product_closure_gate_probe.py" "$@"
    ;;
  ai_nas_search_evidence_contract)
    exec python3 "$script_dir/ai_nas_search_evidence_contract_probe.py" "$@"
    ;;
  ai_nas_search_confidence_calibration_contract)
    exec python3 "$script_dir/ai_nas_search_confidence_calibration_contract_probe.py" "$@"
    ;;
  ai_nas_multimodal_intent_routing_contract)
    exec python3 "$script_dir/ai_nas_multimodal_intent_routing_contract_probe.py" "$@"
    ;;
  ai_nas_semantic_query_acceptance)
    exec python3 "$script_dir/ai_nas_semantic_query_acceptance_probe.py" "$@"
    ;;
  ai_nas_action_approval_manifest)
    exec python3 "$script_dir/ai_nas_action_approval_manifest_probe.py" "$@"
    ;;
  ai_nas_action_manifest_integrity)
    exec python3 "$script_dir/ai_nas_action_manifest_integrity_probe.py" "$@"
    ;;
  ai_nas_operator_approval_inbox)
    exec python3 "$script_dir/ai_nas_operator_approval_inbox_probe.py" "$@"
    ;;
  ai_nas_action_execute_copy)
    exec python3 "$script_dir/ai_nas_action_execute_copy_probe.py" "$@"
    ;;
  ai_nas_action_rollback_copy)
    exec python3 "$script_dir/ai_nas_action_rollback_copy_probe.py" "$@"
    ;;
  ai_nas_destructive_action_governance)
    exec python3 "$script_dir/ai_nas_destructive_action_governance_probe.py" "$@"
    ;;
  ai_nas_audit_trail_contract)
    exec python3 "$script_dir/ai_nas_audit_trail_contract_probe.py" "$@"
    ;;
  ai_nas_permission_aware_search)
    exec python3 "$script_dir/ai_nas_permission_aware_search_probe.py" "$@"
    ;;
  ai_nas_acl_mapping_readiness)
    exec python3 "$script_dir/ai_nas_acl_mapping_readiness_probe.py" "$@"
    ;;
  ai_nas_evidence_report)
    exec python3 "$script_dir/ai_nas_evidence_report_probe.py" "$@"
    ;;
  ai_nas_embedding_search)
    exec python3 "$script_dir/ai_nas_embedding_search_probe.py" "$@"
    ;;
  ai_nas_embedding_backend_readiness)
    exec python3 "$script_dir/ai_nas_embedding_backend_readiness_probe.py" "$@"
    ;;
  ai_nas_embedding_runtime_contract)
    exec python3 "$script_dir/ai_nas_embedding_runtime_contract_probe.py" "$@"
    ;;
  ai_nas_model_service_resilience)
    exec python3 "$script_dir/ai_nas_model_service_resilience_probe.py" "$@"
    ;;
  ai_nas_model_service_recovery_drill)
    exec python3 "$script_dir/ai_nas_model_service_recovery_drill_probe.py" "$@"
    ;;
  ai_nas_model_service_recovery_manifest)
    exec python3 "$script_dir/ai_nas_model_service_recovery_manifest_probe.py" "$@"
    ;;
  ai_nas_model_service_real_recovery_drill)
    exec python3 "$script_dir/ai_nas_model_service_real_recovery_drill_probe.py" "$@"
    ;;
  ai_nas_ocr_runtime_contract)
    exec python3 "$script_dir/ai_nas_ocr_runtime_contract_probe.py" "$@"
    ;;
  ai_nas_ocr_readiness)
    exec python3 "$script_dir/ai_nas_ocr_readiness_probe.py" "$@"
    ;;
  ai_nas_ocr_extract)
    exec python3 "$script_dir/ai_nas_ocr_extract_probe.py" "$@"
    ;;
  ai_nas_document_pipeline_acceptance)
    exec python3 "$script_dir/ai_nas_document_pipeline_acceptance_probe.py" "$@"
    ;;
  ai_nas_file_search)
    exec python3 "$script_dir/ai_nas_file_search_probe.py" "$@"
    ;;
  ai_nas_folder_rag)
    exec python3 "$script_dir/ai_nas_folder_rag_probe.py" "$@"
    ;;
  ai_nas_folder_rag_grounding_contract)
    exec python3 "$script_dir/ai_nas_folder_rag_grounding_contract_probe.py" "$@"
    ;;
  ai_nas_folder_summary)
    exec python3 "$script_dir/ai_nas_folder_summary_probe.py" "$@"
    ;;
  ai_nas_duplicate_report)
    exec python3 "$script_dir/ai_nas_duplicate_report_probe.py" "$@"
    ;;
  ai_nas_photo_similarity)
    exec python3 "$script_dir/ai_nas_photo_similarity_probe.py" "$@"
    ;;
  ai_nas_image_embedding_extract)
    exec python3 "$script_dir/ai_nas_image_embedding_extract_probe.py" "$@"
    ;;
  ai_nas_photo_semantic_search)
    exec python3 "$script_dir/ai_nas_photo_semantic_search_probe.py" "$@"
    ;;
  ai_nas_photo_pipeline_acceptance)
    exec python3 "$script_dir/ai_nas_photo_pipeline_acceptance_probe.py" "$@"
    ;;
  ai_nas_photo_privacy_governance)
    exec python3 "$script_dir/ai_nas_photo_privacy_governance_probe.py" "$@"
    ;;
  ai_nas_movie_sort_enhanced)
    exec python3 "$script_dir/ai_nas_movie_sort_enhanced_probe.py" "$@"
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "Refusing unknown AI-NAS tool ID: $tool_id" >&2
    usage >&2
    exit 2
    ;;
esac
