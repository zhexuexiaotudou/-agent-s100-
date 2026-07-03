# Harness Shadow Probe

- verdict: `failed_harness_shadow_probe`
- generated_at: `2026-07-02T23:27:32.725257+08:00`
- production_path_modified: `False`
- dispatcher_bypassed: `False`
- dream7b_foreground_attached: `False`
- trace_db: `reports\harness_shadow_probe_20260702-232732-545085\harness_runtime_trace.sqlite3`

## Scenarios

- `nas_search_read_only` workspace `nas_search` exposed `1` denied `1` cloud `False` trace `True`
  - context before/after: `15748` -> `1397`
- `nas_denied_acl_search` workspace `nas_search` exposed `1` denied `1` cloud `False` trace `True`
  - context before/after: `15752` -> `1405`
- `nas_destructive_action_requires_approval` workspace `nas_action` exposed `2` denied `1` cloud `False` trace `True`
  - context before/after: `15735` -> `1447`
- `document_report_generation` workspace `document_rag` exposed `2` denied `1` cloud `False` trace `True`
  - context before/after: `15733` -> `1512`
- `web_cloud_research_redacted` workspace `web_cloud_research` exposed `2` denied `1` cloud `True` trace `True`
  - context before/after: `15786` -> `1486`
- `ops_health_check` workspace `ops_recovery` exposed `2` denied `1` cloud `False` trace `True`
  - context before/after: `15740` -> `1576`

## Failures

- `web_cloud_research_redacted:cloud_redaction_failed`
