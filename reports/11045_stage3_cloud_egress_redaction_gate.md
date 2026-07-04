# stage3_cloud_egress_redaction_gate

- verdict: `ok_stage3_cloud_egress_redaction_gate`
- generated_at: `2026-07-04T00:39:25.236082+08:00`
- passed: `6/6`

## Checks

- `PASS` private path leak_count = 0
- `PASS` private filename leak_count = 0
- `PASS` denied snippet leak_count = 0
- `PASS` path hash mapping leak_count = 0
- `PASS` cloud_private_egress_count = 0
- `PASS` raw private payload not stored

## Failures

- none

## Detail

```json
{
  "trace": "reports/stage3_shadow/stage3_cloud_egress_redaction_trace.jsonl",
  "summary": {
    "scenario_count": 6,
    "leak_count": 0,
    "cloud_private_egress_count": 0,
    "raw_private_payload_stored_count": 0
  }
}
```
