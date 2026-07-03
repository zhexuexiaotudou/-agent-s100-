# stage2_6_stage3_shadow_dryrun_go_no_go_gate

- verdict: `failed_stage2_6_stage3_shadow_dryrun_go_no_go_gate`
- generated_at: `2026-07-03T12:29:47.771244+08:00`
- passed: `8/11`

## Checks

- `FAIL` qwen_service_persistence_fixed
- `FAIL` agent_loop_qwen_semantic_success_passed
- `FAIL` agent_loop_soak_passed
- `PASS` readonly_dispatcher_bridge_passed
- `PASS` cloud_private_egress_gate_passed
- `PASS` runtime_trace_complete
- `PASS` rollback_tested
- `PASS` no_write_destructive_tools_enabled
- `PASS` no_production_route_modified
- `PASS` sqlite_remains_default
- `PASS` real_zleap_lab_only_or_skipped

## Failures

- `qwen_service_persistence_fixed`
- `agent_loop_qwen_semantic_success_passed`
- `agent_loop_soak_passed`

## Detail

```json
{
  "conditions": {
    "qwen_service_persistence_fixed": false,
    "agent_loop_qwen_semantic_success_passed": false,
    "agent_loop_soak_passed": false,
    "readonly_dispatcher_bridge_passed": true,
    "cloud_private_egress_gate_passed": true,
    "runtime_trace_complete": true,
    "rollback_tested": true,
    "no_write_destructive_tools_enabled": true,
    "no_production_route_modified": true,
    "sqlite_remains_default": true,
    "real_zleap_lab_only_or_skipped": true
  },
  "dryrun_decision": "C.ready_with_fixes_before_stage3",
  "stage2_5_verdict": "ready_for_more_readonly_sidecar_trials_on_s100p"
}
```
