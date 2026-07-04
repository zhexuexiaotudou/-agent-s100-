# stage4_5_feature_flag_scoped_enable_gate

- verdict: `ok_stage4_5_feature_flag_scoped_enable_gate`
- generated_at: `2026-07-04T13:57:37.529182+08:00`
- passed: `5/5`

## Checks

- `PASS` global execute/rollback flags remain closed
- `PASS` scoped canary flags enable only execute/rollback for this run
- `PASS` scoped enable is bound to candidate fingerprint
- `PASS` operator approval and signed token both present
- `PASS` manifest approval phrase bound to apm manifest

## Failures

- none

## Detail

```json
{
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
  "scoped_canary_flags": {
    "preview_enabled": true,
    "dry_run_enabled": true,
    "confirm_enabled": true,
    "execute_enabled": true,
    "rollback_enabled": true,
    "execute_canary_enabled": true,
    "require_operator_approval_file": true,
    "require_execute_env": true
  },
  "scope": {
    "run_id": "stage4_5_self_created_route_canary_20260704-135733",
    "candidate_fingerprint": "9845850926bccef5ba5aeb9b9d39ada668e9a4a7821958e727f97f6e0d6b62c7",
    "approval_token_hash": "858a01464a848279d81dbe5231c0084c54a45de6966337f546013dfa1e12e63d",
    "manifest_id": "apm-f96cdcaac8399b5c"
  },
  "persistence_boundary": "Scoped flags are in-memory gate state only; configs/copy_route_feature_flags.json is not modified."
}
```
