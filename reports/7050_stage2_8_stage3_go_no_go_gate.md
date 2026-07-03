# stage2_8_stage3_go_no_go_gate

- verdict: `blocked_by_no_operator_approval_for_qwen_persistence`
- generated_at: `2026-07-03T17:24:20.245824+08:00`
- passed: `7/8`

## Checks

- `FAIL` qwen_persistence_applied_and_verified
- `PASS` policy_first_contract_pass
- `PASS` qwen_advisor_pass_or_disabled_safe
- `PASS` readonly_shadow_preflight_soak_pass
- `PASS` no_write_destructive_admin_recovery
- `PASS` no_production_route_change
- `PASS` no_cloud_private_egress
- `PASS` rollback_pass

## Failures

- `qwen_persistence_applied_and_verified`

## Detail

```json
{
  "conditions": {
    "qwen_persistence_applied_and_verified": false,
    "policy_first_contract_pass": true,
    "qwen_advisor_pass_or_disabled_safe": true,
    "readonly_shadow_preflight_soak_pass": true,
    "no_write_destructive_admin_recovery": true,
    "no_production_route_change": true,
    "no_cloud_private_egress": true,
    "rollback_pass": true
  },
  "stage3_go_no_go_verdict": "blocked_by_no_operator_approval_for_qwen_persistence"
}
```
