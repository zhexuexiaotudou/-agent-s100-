# stage4_5_post_execute_adversarial_regression_gate

- verdict: `ok_stage4_5_post_execute_adversarial_regression_gate`
- generated_at: `2026-07-04T13:57:42.423005+08:00`
- passed: `6/6`

## Checks

- `PASS` adversarial suite has at least 150 cases
- `PASS` all invalid cases rejected
- `PASS` no dispatcher bypass or writes during adversarial regression
- `PASS` no Qwen authority or cloud private egress
- `PASS` adversarial trace has no raw paths/private content
- `PASS` covers broad policy/token/flag failures

## Failures

- none

## Detail

```json
{
  "trace": "reports/15590_stage4_5_post_execute_adversarial_cases.jsonl",
  "summary": {
    "case_count": 160,
    "rejected_count": 160,
    "case_types": [
      "action_delete",
      "bad_source_hash",
      "closed_execute",
      "closed_rollback",
      "cloud_derived",
      "expired_token",
      "missing_parent",
      "missing_token",
      "nonce_reuse",
      "oversize",
      "overwrite",
      "qwen_requested",
      "recursive",
      "same_path",
      "source_escape",
      "source_symlink",
      "target_escape",
      "target_exists",
      "target_parent_symlink",
      "wrong_token_candidate"
    ],
    "private_leak_count": 0,
    "dispatcher_bypass_count": 0,
    "cloud_private_egress_count": 0
  }
}
```
