# real_nas_copy_candidate_post_health_gate

- verdict: `ok_real_nas_copy_candidate_post_health_gate`
- generated_at: `2026-07-04T12:03:58.852154+08:00`
- passed: `4/4`

## Checks

- `PASS` remote source remains with expected sha
- `PASS` remote copied target remains absent
- `PASS` OpenClaw health OK post-test
- `PASS` Qwen health OK post-test

## Failures

- none

## Detail

```json
{
  "remote_check": {
    "returncode": 0,
    "elapsed_ms": 211.52,
    "stdout_hash": "e2fe0a4b4524b0c19acba732d4cf0c0200183bea8c2c894766ef86a74db81269",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "__SOURCE__\n78ee7fedc0b1f45ffd4c347c9d9086c10b4a99e80b8645be69c6b7f708c9f5ea  /mnt/nas/openclaw/Personal/Collections/CodexPreflight/source/real_nas_copy_candidate_20260704-120353_source.txt\n__TARGET__\ntarget_missing\n__PORTS__\nLISTEN 0      5          127.0.0.1:18888      0.0.0.0:*                                       \nLISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=854063,fd=3))\nLISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=42831,fd=3)) \n"
  },
  "remote_check_stdout_tail": "__SOURCE__\n78ee7fedc0b1f45ffd4c347c9d9086c10b4a99e80b8645be69c6b7f708c9f5ea  /mnt/nas/openclaw/Personal/Collections/CodexPreflight/source/real_nas_copy_candidate_20260704-120353_source.txt\n__TARGET__\ntarget_missing\n__PORTS__\nLISTEN 0      5          127.0.0.1:18888      0.0.0.0:*                                       \nLISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=854063,fd=3))\nLISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=42831,fd=3)) \n",
  "openclaw": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.716863,
    "json": {
      "ok": true,
      "tool_id": "ai_nas_operator_portal_server",
      "operator_portal_contract": {
        "found": true,
        "filename": "operator_portal_contract.json",
        "path": "/mnt/nas/openclaw/reports/ai_nas_mvp/operator_portal_contract_20260618-160406-445747/operator_portal_contract.json",
        "verdict": "ok_ai_nas_operator_portal_contract",
        "generated_at": "2026-06-18T16:04:08.346324+08:00",
        "selection_policy": "generated_at_then_mtime"
      },
      "portal_html": "/mnt/nas/openclaw/reports/ai_nas_mvp/operator_portal_contract_20260618-160406-445747/operator_portal.html",
      "refresh_on_start": null
    },
    "body_hash": "3f602e957754ba001c367fa58c76c536eda10a7318d8befc265f0d27698f100e",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_tail": ""
  },
  "qwen": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.001004,
    "json": {
      "ok": true,
      "model": "Qwen2.5-1.5B-Instruct-S100P-official",
      "backend": "official-qwen2.5-oellm-multichat-plus-ai-nas-tools",
      "port": 18080,
      "active_profile": "qwen25_7b_instruct_cache_len_1024_q8",
      "priority_profile": "qwen25_7b_instruct_cache_len_1024_q8_vendor_default",
      "priority_status": "promoted_from_shadow_18081",
      "active_hbm": {
        "path": "/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/model/Qwen2.5_1.5B_Instruct_512.hbm",
        "exists": false,
        "size_bytes": 0
      },
      "priority_hbm": {
        "path": "/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_runtime/model/Qwen2.5_1.5B_Instruct_512.hbm",
        "exists": false,
        "size_bytes": 0
      },
      "tool_dispatcher": "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh",
      "report_root": "/mnt/nas/openclaw/reports/qwen25_ai_nas"
    },
    "body_hash": "93f6c14eaa15d5be20371ecd6e2125c3534ad144dc5fcee349d782ded5be1812",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_tail": ""
  }
}
```
