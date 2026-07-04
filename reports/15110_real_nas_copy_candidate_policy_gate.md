# real_nas_copy_candidate_policy_gate

- verdict: `ok_real_nas_copy_candidate_policy_gate`
- generated_at: `2026-07-04T11:48:24.706224+08:00`
- passed: `5/5`

## Checks

- `PASS` first-stage policy is copy-only
- `PASS` target prefix restricted to Personal/Collections
- `PASS` small-file first-stage limit recorded
- `PASS` missing candidate blocks safely
- `PASS` no candidate materialized by Codex

## Failures

- none

## Detail

```json
{
  "candidate_path": null,
  "candidate_load_error": "missing",
  "validation": {
    "candidate_present": false,
    "candidate_valid": false,
    "block_reason": "missing_explicit_candidate",
    "safe_block": true,
    "redacted_candidate": null,
    "candidate_hash": null
  },
  "required_candidate_schema": {
    "action_type": "copy",
    "source_relative_path": "relative to /mnt/nas/openclaw/Personal, no Personal/ prefix, no absolute paths",
    "target_relative_path": "Collections/<reviewed-folder>/<filename>",
    "source_sha256": "64 hex chars from a separate readonly hash probe",
    "expected_size_bytes": "integer <= 1048576",
    "source_owner_scope": "operator_owned or operator_visible",
    "target_exists_now": "false or omitted until immediate pre-execution recheck"
  },
  "future_required_preconditions": [
    "readonly source existence and sha256 verification",
    "readonly target non-existence check",
    "ACL-visible path check for the current operator",
    "signed approval phrase bound to candidate hash and before-state hash",
    "rollback manifest before execution"
  ]
}
```
