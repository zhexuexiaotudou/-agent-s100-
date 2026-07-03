# AI-NAS Operator Portal Contract

- verdict: `failed_ai_nas_operator_portal_contract`
- portal_html: `F:\Project\Digua\reports\operator_portal_contract_20260625-001846-838613\operator_portal.html`
- result_count: `4`
- payment_node_count: `2`
- copy_suggestion_count: `4`
- approval_row_count: `3`
- failures: `['portal_missing_token:dream7b_product_decision_packet', 'portal_missing_token:gateway_fast_ready']`
- policy: static bounded portal only; no execution, network call, service start, delete, move, or overwrite

## Requirement Checks

- single_entry_portal_html: `True`
- official_qwen25_text_route_visible: `False`
- official_s100_vision_route_visible: `False`
- query_visible: `True`
- related_files_visible: `True`
- evidence_visible: `True`
- amount_date_payment_nodes_visible: `True`
- copy_suggestions_visible: `True`
- approval_queue_visible: `True`
- operator_decision_controls_visible: `True`
- one_click_report_visible: `True`
- audit_visible: `True`
- production_readiness_visible: `True`
- soak_completion_gate_watcher_visible: `True`
- dream7b_interaction_visible: `True`
- dream7b_first_response_warning_triage_visible: `True`
- dream7b_service_guardrails_visible: `True`
- dream7b_product_packet_visible: `False`
- dream7b_runtime_experiment_gate_visible: `True`
- dream7b_segment_stability_audit_visible: `True`
- dream7b_segment_drag_breakdown_visible: `True`
- dream7b_group_order_partition_visible: `True`
- dream7b_scheduler_overhead_visible: `True`
- dream7b_runtime_instrumentation_visible: `True`
- dream7b_hbm_load_accounting_visible: `True`
- dream7b_bottleneck_closure_visible: `True`
- dream7b_post_instrumentation_telemetry_gate_visible: `True`
- dream7b_post_instrumentation_overhead_analysis_visible: `True`
- dream7b_post_instrumentation_segment_attribution_visible: `True`
- dream7b_segment_group_schedule_scorecard_visible: `True`
- dream7b_hidden_buffer_reuse_decision_visible: `True`
- dream7b_last_token_compile_gate_visible: `True`
- dream7b_last_token_candidate_visible: `True`
- dream7b_last_token_runtime_validation_visible: `True`
- dream7b_true_batch_nas_inventory_visible: `True`
- dream7b_runtime_refactor_backlog_visible: `True`
- dream7b_default_service_freshness_gate_visible: `True`
- dream7b_default_service_decision_visible: `True`
- dream7b_queue_health_snapshot_visible: `True`
- dream7b_workstream_overlap_audit_visible: `True`
- dream7b_tuning_decision_matrix_visible: `True`
- dream7b_final_logits_leverage_visible: `True`
- dream7b_fast_ready_visible: `False`
- dream7b_rollback_contract_visible: `True`
- dream7b_gateway_listener_match_visible: `True`
- dream7b_gateway_orphan_listener_visible: `True`
- dream7b_gateway_listener_drift_gate_visible: `True`
- dream7b_gateway_listener_drift_match_visible: `True`
- operational_slo_visible: `True`
- slo_limited_evidence_triage_visible: `True`
- objective_traceability_visible: `True`
- production_dependency_bundle_visible: `True`
- production_blocker_runbook_visible: `True`
- no_execution: `True`

## Audit

- source_files_modified: `False`
- real_personal_source_modified: `False`
- delete_performed: `False`
- move_performed: `False`
- overwrite_performed: `False`
- execution_performed: `False`
- all_operations_auditable: `True`
- network_call_performed: `False`
- service_started: `False`
- writes: `bounded fixture files, SQLite index/image_embeddings rows, static HTML portal, Markdown/JSON portal reports`

## Production Gap

- Production still needs a live web/chat surface backed by the mounted NAS and OpenClaw session auth; this contract verifies the required user-facing information model.
