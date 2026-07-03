# memory_boundary_gate

- verdict: `ok_memory_boundary_gate`
- generated_at: `2026-07-02T23:28:15.861883+08:00`
- passed: `11/11`

## Checks

- `PASS` long-term write skipped by default
- `PASS` policy-approved fixture write succeeds
- `PASS` cloud research reads no private memory at privacy none
- `PASS` NAS search can read scoped high privacy memory
- `PASS` nas_search_read_only memory scoped to selected request
- `PASS` nas_denied_acl_search memory scoped to selected request
- `PASS` nas_destructive_action_requires_approval memory scoped to selected request
- `PASS` document_report_generation memory scoped to selected request
- `PASS` web_cloud_research_redacted memory scoped to selected request
- `PASS` ops_health_check memory scoped to selected request
- `PASS` web cloud scenario has no high privacy memory

## Failures

- none
