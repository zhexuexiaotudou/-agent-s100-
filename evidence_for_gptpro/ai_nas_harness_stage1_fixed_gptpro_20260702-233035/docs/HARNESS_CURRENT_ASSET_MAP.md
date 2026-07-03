# AI-NAS Harness Current Asset Map

Generated for Stage 0 / Stage 1 shadow Workspace Harness work. This map is
source-facing and does not change the production path.

## Production Invariants

- Foreground product path stays: OpenClaw portal -> Qwen local gateway -> AI-NAS allowlist dispatcher -> existing probes/gates.
- Harness shadow is default off: `AI_NAS_HARNESS_SHADOW=0`.
- The harness must not bypass `scripts/probes/ai_nas_allowlisted_tool.sh`.
- The harness must not introduce user-selected shell or script paths.
- Dream7B remains historical/experimental and is not attached to the foreground route.
- Protected Dream7B ports `18888` and `18889` are not modified.

## Services And Ports

| Service name | File | Port | Role | Harness action |
| --- | --- | ---: | --- | --- |
| `openclaw-gateway.service` | `configs/systemd/openclaw-gateway.service` | `8765` | AI-NAS Web OS / OpenClaw portal gateway, points to Qwen on `18080` | read-only asset |
| `qwen25-local-openai-gateway.service` | `configs/systemd/qwen25-local-openai-gateway.service` | `18080` | official local Qwen OpenAI-compatible gateway | read-only asset |
| `qwen25-7b-shadow-openai-gateway.service` | `configs/systemd/qwen25-7b-shadow-openai-gateway.service` | `18081` | Qwen 7B shadow gateway, not foreground default | read-only asset |
| `ai-nas-index-daemon.service` | `configs/systemd/ai-nas-index-daemon.service` | none | background SQLite/FTS index daemon | read-only asset |
| `dream7b-local-openai-gateway.service` | `configs/systemd/dream7b-local-openai-gateway.service` | `18888` | historical Dream7B gateway | protected, not used by harness |
| `dream7b-bpu-experimental-gateway-18889.service` | `configs/systemd/dream7b-bpu-experimental-gateway-18889.service` | `18889` | Dream7B experimental gateway | protected, not used by harness |

## Dispatcher

Authoritative dispatcher:
`scripts/probes/ai_nas_allowlisted_tool.sh`

The dispatcher accepts fixed `tool_id` values only. It never evaluates arbitrary
commands or script paths. Workspace Harness Stage 1 wraps this dispatcher and
does not add a second execution surface.

## Dispatcher Tool IDs

Complete active tool list from dispatcher usage and `case` labels:

- `ai_nas_acl_mapping_readiness`
- `ai_nas_action_approval_manifest`
- `ai_nas_action_execute_copy`
- `ai_nas_action_manifest_integrity`
- `ai_nas_action_rollback_copy`
- `ai_nas_allowlist_governance_audit`
- `ai_nas_appliance_experience_acceptance`
- `ai_nas_audit_trail_contract`
- `ai_nas_bpu_headroom_slo`
- `ai_nas_case_packet`
- `ai_nas_concurrency_stability`
- `ai_nas_continuous_task_soak`
- `ai_nas_controlled_personal_seed`
- `ai_nas_destructive_action_governance`
- `ai_nas_document_pipeline_acceptance`
- `ai_nas_duplicate_report`
- `ai_nas_edge_cloud_router`
- `ai_nas_embedding_backend_readiness`
- `ai_nas_embedding_runtime_contract`
- `ai_nas_embedding_search`
- `ai_nas_evidence_catalog_contract`
- `ai_nas_evidence_freshness_contract`
- `ai_nas_evidence_report`
- `ai_nas_file_search`
- `ai_nas_folder_rag`
- `ai_nas_folder_rag_grounding_contract`
- `ai_nas_folder_summary`
- `ai_nas_goal_completion_audit`
- `ai_nas_goal_completion_finalizer`
- `ai_nas_image_embedding_extract`
- `ai_nas_incremental_scan_efficiency_contract`
- `ai_nas_index_daemon_readiness`
- `ai_nas_index_daemon_resident`
- `ai_nas_index_daemon_smoke`
- `ai_nas_index_observability_contract`
- `ai_nas_index_rename_detection`
- `ai_nas_index_search_isolation_slo`
- `ai_nas_index_status`
- `ai_nas_index_systemd_daemon_install`
- `ai_nas_model_service_real_recovery_drill`
- `ai_nas_model_service_recovery_drill`
- `ai_nas_model_service_recovery_manifest`
- `ai_nas_model_service_resilience`
- `ai_nas_movie_sort_enhanced`
- `ai_nas_multimodal_intent_routing_contract`
- `ai_nas_nas_backed_long_soak`
- `ai_nas_objective_traceability_contract`
- `ai_nas_ocr_extract`
- `ai_nas_ocr_readiness`
- `ai_nas_ocr_runtime_contract`
- `ai_nas_official_ppocr_wrapper`
- `ai_nas_official_route_readiness_gate`
- `ai_nas_operational_slo_rollup_contract`
- `ai_nas_operator_approval_inbox`
- `ai_nas_operator_portal_contract`
- `ai_nas_operator_portal_server`
- `ai_nas_perf_benchmark`
- `ai_nas_permission_aware_search`
- `ai_nas_personal_inventory`
- `ai_nas_photo_pipeline_acceptance`
- `ai_nas_photo_privacy_governance`
- `ai_nas_photo_semantic_search`
- `ai_nas_photo_similarity`
- `ai_nas_portable_nas_adapter_contract`
- `ai_nas_product_closure_gate`
- `ai_nas_production_blocker_runbook_contract`
- `ai_nas_production_dependency_bundle`
- `ai_nas_production_readiness_gate`
- `ai_nas_queue_backpressure_slo`
- `ai_nas_search_confidence_calibration_contract`
- `ai_nas_search_evidence_contract`
- `ai_nas_semantic_query_acceptance`
- `ai_nas_soak_checkpoint_resume`
- `ai_nas_soak_completion_gate_watcher`
- `ai_nas_sqlite_index_integrity_contract`
- `ai_nas_task_queue`
- `ai_nas_user_facing_tail_latency`
- `dream7b_perf_identity`

Harness policy does not expose `dream7b_perf_identity` to any workspace.

## Workspace Tool Partitions

| Workspace | Cloud | Write | Tool exposure |
| --- | --- | --- | --- |
| `main_router` | no | no | route classification only |
| `nas_search` | no | no | read-only inventory/search/index/RAG-summary tools |
| `nas_action` | no | yes | approval manifest, copy rollback, audit trail; execution tools require approval |
| `media_photo` | no | no | photo, image embedding, duplicate and movie classification tools |
| `document_rag` | no | no | OCR, folder RAG, case packet, evidence report tools |
| `ops_recovery` | no | no | daemon, queue, SLO, model-service recovery manifest/drill tools; recovery tools require approval |
| `web_cloud_research` | yes | no | router and public/redacted evidence catalog tools only |
| `admin_audit` | no | no | governance, audit, readiness and closure gates |

## Existing Gate IDs

Core current-route gate/verdict IDs from `README.md` and source:

- `ok_qwen25_ai_nas_acceptance_packet`
- `ok_qwen25_ai_nas_gateway_turn`
- `ok_qwen25_7b_shadow_acceptance_packet`
- `ok_ai_nas_openclaw_nas_control_gate`
- `ok_ai_nas_edge_cloud_router`
- `ok_ai_nas_product_closure_gate`
- `ok_ai_nas_production_readiness_gate`
- `ok_ai_nas_official_route_readiness_gate`
- `ok_ai_nas_allowlist_governance`

AI-NAS source-scanned gate/verdict IDs:

- `ok_ai_nas_7b_unified_gate`
- `ok_ai_nas_action_manifest_integrity`
- `ok_ai_nas_appliance_experience_acceptance`
- `ok_ai_nas_audit_trail_contract`
- `ok_ai_nas_bpu_headroom_slo`
- `ok_ai_nas_chinese_search_gate`
- `ok_ai_nas_competition_final_acceptance`
- `ok_ai_nas_concurrency_stability`
- `ok_ai_nas_continuous_task_soak`
- `ok_ai_nas_controlled_personal_seed`
- `ok_ai_nas_copilot_product_gate`
- `ok_ai_nas_destructive_action_governance`
- `ok_ai_nas_doc_rag_gate`
- `ok_ai_nas_document_pipeline_acceptance`
- `ok_ai_nas_duplicate_report`
- `ok_ai_nas_embedding_backend_readiness`
- `ok_ai_nas_embedding_runtime_contract`
- `ok_ai_nas_embedding_search`
- `ok_ai_nas_evidence_catalog_contract`
- `ok_ai_nas_evidence_freshness_contract`
- `ok_ai_nas_file_search`
- `ok_ai_nas_folder_rag`
- `ok_ai_nas_folder_rag_grounding_contract`
- `ok_ai_nas_goal_completion_audit`
- `ok_ai_nas_goal_completion_finalizer`
- `ok_ai_nas_image_embedding_extract`
- `ok_ai_nas_incremental_scan_efficiency_contract`
- `ok_ai_nas_index_daemon_readiness`
- `ok_ai_nas_index_daemon_resident`
- `ok_ai_nas_index_daemon_smoke`
- `ok_ai_nas_index_observability_contract`
- `ok_ai_nas_index_rename_detection`
- `ok_ai_nas_index_search_isolation_slo`
- `ok_ai_nas_index_systemd_daemon_install`
- `ok_ai_nas_llm_caption_visual_search_gate`
- `ok_ai_nas_media_enhanced_portal_gate`
- `ok_ai_nas_model_service_real_recovery_drill`
- `ok_ai_nas_model_service_recovery_manifest`
- `ok_ai_nas_movie_sort_enhanced`
- `ok_ai_nas_multimodal_intent_routing_contract`
- `ok_ai_nas_multimodal_product_completion_gate`
- `ok_ai_nas_nas_backed_long_soak`
- `ok_ai_nas_objective_traceability_contract`
- `ok_ai_nas_ocr_extract`
- `ok_ai_nas_ocr_runtime_contract`
- `ok_ai_nas_official_ppocr_document_bridge`
- `ok_ai_nas_official_ppocr_wrapper`
- `ok_ai_nas_official_vision_route_demo_ready`
- `ok_ai_nas_operational_slo_rollup_contract`
- `ok_ai_nas_operator_approval_inbox`
- `ok_ai_nas_operator_portal_contract`
- `ok_ai_nas_perf_benchmark`
- `ok_ai_nas_permission_aware_search`
- `ok_ai_nas_personal_root_integration_gate`
- `ok_ai_nas_photo_pipeline_acceptance`
- `ok_ai_nas_photo_privacy_governance`
- `ok_ai_nas_portable_nas_adapter_contract`
- `ok_ai_nas_product_embedding_region_gate`
- `ok_ai_nas_product_ocr_adapter_gate`
- `ok_ai_nas_product_visual_acl_evidence_gate`
- `ok_ai_nas_product_visual_search_contract_gate`
- `ok_ai_nas_production_blocker_runbook_contract`
- `ok_ai_nas_production_dependency_bundle`
- `ok_ai_nas_pwa_mobile_portal_gate`
- `ok_ai_nas_queue_backpressure_slo`
- `ok_ai_nas_real_acl_mapping_gate`
- `ok_ai_nas_report_photo_movie_gate`
- `ok_ai_nas_route_a_demo_readiness_packet`
- `ok_ai_nas_s100_clip_realdata_gate`
- `ok_ai_nas_s100_grounded_vision_realdata_gate`
- `ok_ai_nas_scheduled_rules_portal_gate`
- `ok_ai_nas_search_confidence_calibration_contract`
- `ok_ai_nas_search_evidence_contract`
- `ok_ai_nas_semantic_image_search_gate`
- `ok_ai_nas_semantic_query_acceptance`
- `ok_ai_nas_settings_portal_gate`
- `ok_ai_nas_soak_checkpoint_resume`
- `ok_ai_nas_soak_completion_gate_watcher`
- `ok_ai_nas_sqlite_index_integrity_contract`
- `ok_ai_nas_user_facing_tail_latency`
- `ok_ai_nas_vision_adapter_registry_gate`
- `ok_ai_nas_visual_index_generation_gate`
- `ok_ai_nas_visual_product_foundation_gate`
- `ok_ai_nas_visual_search_gate`

Non-`ok_ai_nas_*` NAS gate/verdict IDs:

- `ok_nas_acl_identity_gate`
- `ok_nas_app_ecosystem_gate`
- `ok_nas_backup_sync_gate`
- `ok_nas_integrated_portal_gate`
- `ok_nas_media_center_gate`
- `ok_nas_ops_observability_gate`
- `ok_nas_snapshot_recovery_gate`
- `ok_nas_storage_foundation_gate`
- `ok_nas_web_os_gate`
- `ok_top_nas_replacement_product_gate`

Dream7B gate/verdict IDs remain historical or experimental assets and are not
workspace-exposed in Stage 1. Examples include `ok_dream7b_perf_identity`,
`ok_dream7b_seq128_s100p_runtime_gate`, and
`ok_dream7b_product_decision_packet`.

## Stage 1 Harness Gate IDs

New Stage 1 gate IDs:

- `workspace_isolation_gate`
- `tool_exposure_minimization_gate`
- `memory_boundary_gate`
- `runtime_trace_completeness_gate`
- `cloud_egress_redaction_gate`
- `harness_stage1_gate_report`

## Report Schemas

Common existing probe/gate JSON schema:

- `generated_at`: ISO timestamp.
- `tool_id`: dispatcher or probe tool identifier.
- `verdict`: `ok_*`, `failed_*`, `partial_*`, `ready_*`, or `limited_*`.
- `summary`: aggregate route/check/report counts when present.
- `checks`: list of `{label, ok}` check records when present.
- `failures` / `errors`: failing condition list.
- `audit`: source modification and write-policy record when present.
- `report_paths` / `reports` / `paths`: emitted evidence files.

Qwen gateway turn schema:

- `verdict`: `ok_qwen25_ai_nas_gateway_turn` or failure verdict.
- `query`: original request preview.
- `tool_runs`: fixed dispatcher calls for evidence report, case packet, folder RAG and inventory.
- `report_paths`: generated Markdown/JSON evidence reports.
- `metadata`: route and model metadata returned by the gateway.

Edge/cloud router schema:

- `tool_id`: `ai_nas_edge_cloud_router`.
- `verdict`: `ok_ai_nas_edge_cloud_router` or failure.
- `audit_events`: per-query route, privacy level, classifier, and cloud-call record.
- `summary.privacy_query_sent_to_cloud`: must be false.
- `controlled_cloud_calls`: local stub call records when used.

OpenClaw NAS control gate schema:

- `tool_id`: `ai_nas_openclaw_nas_control_gate`.
- `verdict`: `ok_ai_nas_openclaw_nas_control_gate` or failure.
- `checks`: portal, login, NAS list/rename/copy/delete-confirmation/ACL checks.
- `artifacts`: action details and temporary local URLs.

Stage 1 runtime trace schema:

- `harness_runs`: run id, scenario id, selected workspace, status.
- `harness_steps`: step type, status, detail JSON.
- `workspace_decisions`: selected workspace, reason, confidence, alternatives.
- `tool_calls`: workspace, tool id, status, args, result, dispatcher boundary flag.
- `policy_denials`: denied tool id, reason, requested args.
- `memory_reads`: memory type, scope, privacy level, record count.
- `gate_results`: gate id, verdict, detail JSON.

## Stage 1 Report Outputs

- Shadow probe JSON/Markdown:
  `reports/harness_shadow_probe_latest.json`,
  `reports/harness_shadow_probe_latest.md`.
- Runtime trace JSON/Markdown:
  `reports/harness_shadow_probe_*/harness_runtime_trace.json`,
  `reports/harness_shadow_probe_*/harness_runtime_trace.md`.
- Combined Stage 1 gate report:
  `reports/harness_stage1_gate_report.json`,
  `reports/harness_stage1_gate_report.md`.
- Final summary:
  `docs/HARNESS_STAGE1_RESULTS.md`.

## Asset Boundary Notes

- `ai_nas_openclaw_nas_control_gate_probe.py` is an existing gate asset, not a
  dispatcher-exposed `tool_id` in the current `ai_nas_allowlisted_tool.sh`.
- `dream7b_perf_identity` is dispatcher-exposed historically, but Stage 1
  workspace policy intentionally exposes it to no workspace.
- Remote S100P acceptance packets under `/mnt/nas/openclaw/reports/...` are
  referenced as current production evidence in `README.md`; Stage 1 local
  harness does not rewrite those reports.
