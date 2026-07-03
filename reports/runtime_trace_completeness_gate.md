# runtime_trace_completeness_gate

- verdict: `ok_runtime_trace_completeness_gate`
- generated_at: `2026-07-02T23:28:15.864120+08:00`
- passed: `19/19`

## Checks

- `PASS` trace DB exists
- `PASS` harness_runs has rows
- `PASS` harness_steps has rows
- `PASS` workspace_decisions has rows
- `PASS` tool_calls has rows
- `PASS` policy_denials has rows
- `PASS` memory_reads has rows
- `PASS` gate_results has rows
- `PASS` six trace runs recorded
- `PASS` nas_search_read_only trace complete
- `PASS` nas_denied_acl_search trace complete
- `PASS` nas_destructive_action_requires_approval trace complete
- `PASS` document_report_generation trace complete
- `PASS` web_cloud_research_redacted trace complete
- `PASS` ops_health_check trace complete
- `PASS` denied calls recorded
- `PASS` policy_denials recorded
- `PASS` all tool call records preserve dispatcher boundary
- `PASS` shadow probe verdict ok

## Failures

- none
