# qwen_runtime_identity_gate

- verdict: `ok_qwen_runtime_identity_gate`
- generated_at: `2026-07-03T01:33:39.365061+08:00`
- passed: `4/4`

## Checks

- `PASS` gateway callable or explicitly unavailable
- `PASS` model id recorded
- `PASS` backend or fallback recorded or unknown
- `PASS` sidecar provider points to local Qwen

## Failures

- none

## Detail

```json
{
  "health": {
    "ok": false,
    "status": 0,
    "error": "URLError:<urlopen error [WinError 10061] 由于目标计算机积极拒绝，无法连接。>"
  },
  "models": {
    "ok": false,
    "status": 0,
    "error": "URLError:<urlopen error [WinError 10061] 由于目标计算机积极拒绝，无法连接。>"
  },
  "model_id": "unknown",
  "provider_config": {
    "version": "stage2_sidecar_provider_v1",
    "default_provider": "qwen25_local",
    "providers": {
      "qwen25_local": {
        "base_url": "http://127.0.0.1:18080/v1",
        "model": "Qwen2.5-1.5B-Instruct-S100P-official",
        "allow_cloud": false
      }
    },
    "sidecar": {
      "bind": "127.0.0.1",
      "port": 19080,
      "default_enabled": false,
      "foreground_route": false
    }
  }
}
```
