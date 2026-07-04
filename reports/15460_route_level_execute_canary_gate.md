# route_level_execute_canary_gate

- verdict: `route_execute_canary_blocked_by_missing_approval_or_flag`
- generated_at: `2026-07-04T12:31:21.658173+08:00`
- passed: `4/4`

## Checks

- `PASS` execute canary blocked safely by default
- `PASS` rollback blocked safely by default
- `PASS` no execute or rollback writes performed
- `PASS` execute canary trace redacted

## Failures

- none

## Detail

```json
{
  "trace": "reports/stage4_4_route_execute_canary_trace.jsonl",
  "env_enabled": false,
  "approval_file": "operator_approval/stage4_4_route_execute_canary_approved.json",
  "approval_file_present": false,
  "operator_approved": false,
  "feature_flags": {
    "preview_enabled": true,
    "dry_run_enabled": true,
    "confirm_enabled": true,
    "execute_enabled": false,
    "rollback_enabled": false,
    "execute_canary_enabled": false,
    "require_operator_approval_file": true,
    "require_execute_env": true
  },
  "execute_status": "execute_blocked",
  "execute_reason_codes": [
    "approval_token_missing",
    "execute_env_not_enabled",
    "execute_feature_disabled",
    "operator_approval_file_missing",
    "operator_approval_missing"
  ]
}
```
