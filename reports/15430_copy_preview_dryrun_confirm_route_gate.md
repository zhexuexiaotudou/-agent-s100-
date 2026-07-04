# copy_preview_dryrun_confirm_route_gate

- verdict: `ok_copy_preview_dryrun_confirm_route_gate`
- generated_at: `2026-07-04T12:31:21.418708+08:00`
- passed: `5/5`

## Checks

- `PASS` preview/dry-run/confirm all allowed
- `PASS` no route writes performed
- `PASS` confirm issued signed token
- `PASS` route responses and audit are redacted
- `PASS` execute and rollback not invoked in route gate

## Failures

- none

## Detail

```json
{
  "trace": "reports/stage4_4_copy_route_preview_dryrun_trace.jsonl",
  "trace_rows": 3,
  "candidate_fingerprint": "009a70122418c805eae46118024a549a8fb8100bf84ec156bae8578c9b281881",
  "token_hash": "28d227550ff9816d26b6073c52645e4dd91273bc07d9e567d7ed2033a5410f01"
}
```
