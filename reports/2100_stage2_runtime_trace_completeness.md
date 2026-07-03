# stage2_runtime_trace_completeness_gate

- verdict: `ok_stage2_runtime_trace_completeness_gate`
- generated_at: `2026-07-03T01:33:40.393611+08:00`
- passed: `3/3`

## Checks

- `PASS` every run has trace
- `PASS` trace complete rate >= 0.99
- `PASS` no raw private args in trace

## Failures

- none

## Detail

```json
{
  "trace_jsonl": "reports\\stage2_sidecar_runtime_trace.jsonl",
  "trace_complete_rate": 1.0,
  "run_count": 16
}
```
