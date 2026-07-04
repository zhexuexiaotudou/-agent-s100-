# stage4_5_pre_execute_route_flow_gate

- verdict: `ok_stage4_5_pre_execute_route_flow_gate`
- generated_at: `2026-07-04T13:57:37.525786+08:00`
- passed: `6/6`

## Checks

- `PASS` candidate exists for route flow
- `PASS` preview/dry-run/confirm allowed
- `PASS` signed approval token issued by confirm
- `PASS` execute remains blocked under default global flags
- `PASS` pre-execute route flow performed no writes
- `PASS` pre-execute route trace has no raw paths/private content

## Failures

- none

## Detail

```json
{
  "trace": "reports/stage4_5_pre_execute_route_flow_trace.jsonl",
  "global_feature_flags": {
    "preview_enabled": true,
    "dry_run_enabled": true,
    "confirm_enabled": true,
    "execute_enabled": false,
    "rollback_enabled": false,
    "execute_canary_enabled": false,
    "require_operator_approval_file": true,
    "require_execute_env": true
  },
  "approval_token_hash": "858a01464a848279d81dbe5231c0084c54a45de6966337f546013dfa1e12e63d",
  "route_statuses": {
    "preview": "preview_allowed",
    "dry-run": "dry-run_allowed",
    "confirm": "confirm_allowed_token_issued",
    "execute_default_closed": "execute_blocked"
  },
  "execute_default_reason_codes": [
    "execute_feature_disabled"
  ]
}
```
