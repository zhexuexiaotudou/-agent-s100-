# stage2_sidecar_mock_isolation_gate

- verdict: `ok_stage2_sidecar_mock_isolation_gate`
- generated_at: `2026-07-03T01:33:40.388097+08:00`
- passed: `4/4`

## Checks

- `PASS` sidecar health ok
- `PASS` sidecar uses non-protected port
- `PASS` mock read-only tools only
- `PASS` protected service hashes unchanged

## Failures

- none

## Detail

```json
{
  "port": 63771,
  "stdout": "{\"listening\": \"http://127.0.0.1:63771\", \"provider_base_url\": \"http://127.0.0.1:18080/v1\"}\n",
  "stderr": ""
}
```
