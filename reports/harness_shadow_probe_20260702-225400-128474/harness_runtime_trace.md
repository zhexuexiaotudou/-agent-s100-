# AI-NAS Harness Runtime Trace

- generated_at: `2026-07-02T22:54:00.277375+08:00`
- runtime_trace_db: `reports\harness_shadow_probe_20260702-225400-128474\harness_runtime_trace.sqlite3`

## Table Counts

- harness_runs: `6`
- harness_steps: `6`
- workspace_decisions: `6`
- tool_calls: `16`
- policy_denials: `7`
- memory_reads: `6`
- gate_results: `6`

## Runs

- `hr-e11835149dac4e53` scenario `nas_search_read_only` workspace `nas_search` status `ok`
- `hr-e63e747c319e4f02` scenario `nas_denied_acl_search` workspace `nas_search` status `ok`
- `hr-07d11ba69b5049fb` scenario `nas_destructive_action_requires_approval` workspace `nas_action` status `ok`
- `hr-276dc43b13e2425c` scenario `document_report_generation` workspace `document_rag` status `ok`
- `hr-6e44c56baad34c56` scenario `web_cloud_research_redacted` workspace `web_cloud_research` status `ok`
- `hr-37dac38678314d10` scenario `ops_health_check` workspace `ops_recovery` status `ok`

## Policy Denials

- `nas_search` denied `ai_nas_action_execute_copy`: tool_not_allowed_in_workspace
- `nas_search` denied `ai_nas_audit_trail_contract`: tool_not_allowed_in_workspace
- `nas_action` denied `ai_nas_action_execute_copy`: approval_required
- `nas_action` denied `ai_nas_file_search`: tool_not_allowed_in_workspace
- `document_rag` denied `ai_nas_photo_semantic_search`: tool_not_allowed_in_workspace
- `web_cloud_research` denied `ai_nas_file_search`: tool_not_allowed_in_workspace
- `ops_recovery` denied `dream7b_perf_identity`: tool_not_allowed_in_workspace
