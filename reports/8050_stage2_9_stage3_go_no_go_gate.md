# stage2_9_stage3_go_no_go_gate

- verdict: `blocked_by_no_operator_approval_for_qwen_persistence`
- generated_at: `2026-07-03T23:44:11.796075+08:00`
- passed: `6/12`

## Checks

- `FAIL` operator_approved
- `FAIL` qwen_persistence_applied_and_verified
- `FAIL` service_active_enabled
- `FAIL` restart_ok
- `PASS` rollback_plan_verified
- `PASS` policy_first_contract_inherited_pass
- `PASS` advisor_disabled_or_optional_non_authoritative
- `FAIL` post_persistence_soak_pass
- `PASS` no_write_destructive_admin_recovery
- `PASS` no_production_route_change
- `PASS` no_cloud_private_egress
- `FAIL` openclaw_qwen_health_pass

## Failures

- `operator_approved`
- `qwen_persistence_applied_and_verified`
- `service_active_enabled`
- `restart_ok`
- `post_persistence_soak_pass`
- `openclaw_qwen_health_pass`

## Detail

```json
{
  "conditions": {
    "operator_approved": false,
    "qwen_persistence_applied_and_verified": false,
    "service_active_enabled": false,
    "restart_ok": false,
    "rollback_plan_verified": true,
    "policy_first_contract_inherited_pass": true,
    "advisor_disabled_or_optional_non_authoritative": true,
    "post_persistence_soak_pass": false,
    "no_write_destructive_admin_recovery": true,
    "no_production_route_change": true,
    "no_cloud_private_egress": true,
    "openclaw_qwen_health_pass": false
  },
  "stage3_go_no_go_verdict": "blocked_by_no_operator_approval_for_qwen_persistence"
}
```
