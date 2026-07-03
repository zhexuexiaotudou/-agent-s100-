# AI-NAS Harness Runtime Trace

- generated_at: `2026-07-02T22:49:08.225086+08:00`
- runtime_trace_db: `reports\harness_shadow_probe_20260702-224907-985752\harness_runtime_trace.sqlite3`

## Table Counts

- harness_runs: `6`
- harness_steps: `6`
- workspace_decisions: `6`
- tool_calls: `16`
- policy_denials: `7`
- memory_reads: `6`
- gate_results: `6`

## Runs

- `hr-496bc80e4880401b` scenario `nas_search_read_only` workspace `nas_search` status `ok`
- `hr-bf8cf58d2aef4c51` scenario `nas_denied_acl_search` workspace `nas_search` status `ok`
- `hr-5a49bf4b8b7443e1` scenario `nas_destructive_action_requires_approval` workspace `nas_action` status `ok`
- `hr-a568c5d0d75a4ed6` scenario `document_report_generation` workspace `document_rag` status `ok`
- `hr-1efc25138cc8488f` scenario `web_cloud_research_redacted` workspace `web_cloud_research` status `ok`
- `hr-1de5db85b6954fe2` scenario `ops_health_check` workspace `ops_recovery` status `ok`

## Policy Denials

- `nas_search` denied `ai_nas_action_execute_copy`: tool_not_allowed_in_workspace
- `nas_search` denied `ai_nas_audit_trail_contract`: tool_not_allowed_in_workspace
- `nas_action` denied `ai_nas_action_execute_copy`: approval_required
- `nas_action` denied `ai_nas_file_search`: tool_not_allowed_in_workspace
- `document_rag` denied `ai_nas_photo_semantic_search`: tool_not_allowed_in_workspace
- `web_cloud_research` denied `ai_nas_file_search`: tool_not_allowed_in_workspace
- `ops_recovery` denied `dream7b_perf_identity`: tool_not_allowed_in_workspace
