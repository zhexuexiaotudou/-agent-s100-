# stage2_context_minimization_regression_gate

- verdict: `ok_stage2_context_minimization_regression_gate`
- generated_at: `2026-07-03T01:33:40.393880+08:00`
- passed: `3/3`

## Checks

- `PASS` no global catalog exposure
- `PASS` sidecar context <= stage1 * 1.20
- `PASS` sidecar exposed tool count bounded

## Failures

- none

## Detail

```json
{
  "comparisons": [
    {
      "scenario": "nas_search_read_only",
      "stage1_context": 1397,
      "stage2_estimated_context": 1466,
      "stage1_exposed": 1,
      "stage2_exposed": 3
    },
    {
      "scenario": "nas_denied_acl_search",
      "stage1_context": 1405,
      "stage2_estimated_context": 1475,
      "stage1_exposed": 1,
      "stage2_exposed": 3
    },
    {
      "scenario": "document_report_generation",
      "stage1_context": 1512,
      "stage2_estimated_context": 1587,
      "stage1_exposed": 2,
      "stage2_exposed": 5
    }
  ]
}
```
