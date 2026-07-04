# stage4_signed_approval_token_gate

- verdict: `ok_stage4_signed_approval_token_gate`
- generated_at: `2026-07-04T11:22:14.032264+08:00`
- passed: `5/5`

## Checks

- `PASS` token schema written
- `PASS` valid sandbox token accepted
- `PASS` invalid variants rejected
- `PASS` required target/before/rollback/human fields enforced
- `PASS` real NAS tool/workspace rejected

## Failures

- none

## Detail

```json
{
  "schema": "config/stage4_sandbox_approval_token_schema.json",
  "test_results": [
    {
      "name": "valid",
      "ok": true,
      "reason": "ok"
    },
    {
      "name": "expired",
      "ok": false,
      "reason": "expired"
    },
    {
      "name": "wrong_tool",
      "ok": false,
      "reason": "tool_not_allowlisted_for_sandbox"
    },
    {
      "name": "wrong_workspace",
      "ok": false,
      "reason": "workspace_not_sandbox"
    },
    {
      "name": "missing_rollback",
      "ok": false,
      "reason": "missing:rollback_plan_hash"
    },
    {
      "name": "wrong_confirmation",
      "ok": false,
      "reason": "human_confirmation_missing_or_wrong"
    },
    {
      "name": "bad_signature",
      "ok": false,
      "reason": "bad_signature"
    },
    {
      "name": "nonce_reuse",
      "ok": false,
      "reason": "nonce_reuse"
    }
  ],
  "accepted_count": 1,
  "rejected_count": 7
}
```
