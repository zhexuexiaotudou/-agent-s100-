# approval_token_schema_gate

- verdict: `ok_approval_token_schema_gate`
- generated_at: `2026-07-03T01:33:35.238425+08:00`
- passed: `6/6`

## Checks

- `PASS` unsigned token rejected
- `PASS` expired token rejected
- `PASS` wrong tool rejected
- `PASS` wrong args rejected
- `PASS` correct token accepted only in test mode
- `PASS` correct token does not unlock stage2 write mode

## Failures

- none

## Detail

```json
{
  "token_schema_fields": [
    "action_type",
    "approval_id",
    "args_hash",
    "expires_at",
    "nonce",
    "signature",
    "tool_id",
    "user_id",
    "workspace_id"
  ]
}
```
