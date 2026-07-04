# stage3_final_gate_packet

- verdict: `stage3_readonly_shadow_pass_but_hold_for_longer_soak`
- generated_at: `2026-07-04T00:39:26.192441+08:00`
- passed: `9/9`

## Checks

- `PASS` baseline_lock_pass
- `PASS` shadow_tap_pass
- `PASS` policy_first_decision_pass
- `PASS` readonly_execution_pass
- `PASS` health_resource_latency_pass
- `PASS` cloud_redaction_pass
- `PASS` rollback_pass
- `PASS` stage4_not_entered
- `PASS` write_actions_not_enabled

## Failures

- none

## Detail

```json
{
  "conditions": {
    "baseline_lock_pass": true,
    "shadow_tap_pass": true,
    "policy_first_decision_pass": true,
    "readonly_execution_pass": true,
    "health_resource_latency_pass": true,
    "cloud_redaction_pass": true,
    "rollback_pass": true,
    "stage4_not_entered": true,
    "write_actions_not_enabled": true
  },
  "final_verdict": "stage3_readonly_shadow_pass_but_hold_for_longer_soak"
}
```
