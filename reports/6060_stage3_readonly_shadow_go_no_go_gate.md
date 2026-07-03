# stage2_7_stage3_readonly_shadow_go_no_go_gate

- verdict: `failed_stage2_7_stage3_readonly_shadow_go_no_go_gate`
- generated_at: `2026-07-03T13:03:11.524546+08:00`
- passed: `11/12`

## Checks

- `PASS` package_self_rerun_pass
- `FAIL` qwen_service_persistence_fully_fixed
- `PASS` structured_contract_or_policy_first_claim
- `PASS` qwen_driven_soak_pass_if_claiming_qwen_driven
- `PASS` readonly_dispatcher_bridge_pass
- `PASS` cloud_private_leak_count_zero
- `PASS` runtime_trace_complete
- `PASS` rollback_pass
- `PASS` no_write_destructive_admin_recovery_tools
- `PASS` no_production_route_change
- `PASS` sqlite_remains_default
- `PASS` zleap_lab_only_or_skipped

## Failures

- `qwen_service_persistence_fully_fixed`

## Detail

```json
{
  "conditions": {
    "package_self_rerun_pass": true,
    "qwen_service_persistence_fully_fixed": false,
    "structured_contract_or_policy_first_claim": true,
    "qwen_driven_soak_pass_if_claiming_qwen_driven": true,
    "readonly_dispatcher_bridge_pass": true,
    "cloud_private_leak_count_zero": true,
    "runtime_trace_complete": true,
    "rollback_pass": true,
    "no_write_destructive_admin_recovery_tools": true,
    "no_production_route_change": true,
    "sqlite_remains_default": true,
    "zleap_lab_only_or_skipped": true
  },
  "architecture_decision": "policy_first_deterministic_router_with_qwen_summarizer_advisor",
  "stage3_go_no_go_verdict": "ready_with_fixes_before_stage3"
}
```
