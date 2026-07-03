# stage2_s100p_sidecar_isolation_gate

- verdict: `ok_stage2_s100p_sidecar_isolation_gate`
- generated_at: `2026-07-03T01:38:13.290719+08:00`
- passed: `6/6`

## Checks

- `PASS` sidecar starts on isolated localhost port
- `PASS` provider points to local Qwen
- `PASS` only read-only sidecar tools exposed
- `PASS` OpenClaw health unchanged after sidecar start
- `PASS` Qwen health unchanged after sidecar start
- `PASS` protected hashes unchanged

## Failures

- none

## Detail

```json
{
  "remote_root": "/tmp/digua_stage2_s100p_live_20260703-013757",
  "port": 19081,
  "start": {
    "scp_mock_server": {
      "returncode": 0,
      "elapsed_ms": null,
      "stdout_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_tail": ""
    },
    "scp_mock_tools": {
      "returncode": 0,
      "elapsed_ms": null,
      "stdout_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_tail": ""
    },
    "start": {
      "returncode": 0,
      "elapsed_ms": 1224.198,
      "stdout_hash": "76e20ed479a5a1dd16aa92a1fff83ee32a46cf6335d7eba7a99cd60d42c4f194",
      "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_tail": "{\"ok\": true, \"runtime\": \"stage2_sidecar_mock\", \"foreground_route\": false, \"provider_base_url\": \"http://127.0.0.1:18080/v1\", \"tools\": [\"mock.nas_search\", \"mock.document_rag\"]}"
    }
  },
  "tools": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.001088,
    "json": {
      "version": "stage2_sidecar_mock_tools_v1",
      "tools": [
        {
          "id": "mock.nas_search",
          "workspace_id": "nas_search",
          "read_only": true,
          "write_allowed": false
        },
        {
          "id": "mock.document_rag",
          "workspace_id": "document_rag",
          "read_only": true,
          "write_allowed": false
        }
      ]
    },
    "body_hash": "2336d368aa3e6816ccdc05d1383f84d08e0f2164149294ab2cd89a69515c5ec6",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_tail": ""
  }
}
```
