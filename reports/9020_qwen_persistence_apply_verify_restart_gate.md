# stage2_10_qwen_persistence_apply_verify_restart_gate

- verdict: `ok_stage2_10_qwen_persistence_apply_verify_restart_gate`
- generated_at: `2026-07-04T00:08:06.859425+08:00`
- passed: `9/9`

## Checks

- `PASS` operator approved = true
- `PASS` pre-apply Qwen/OpenClaw health OK
- `PASS` pre-apply hashes recorded
- `PASS` unit installed and service active/enabled
- `PASS` Qwen health and /v1/models OK after restart
- `PASS` OpenClaw health OK after restart
- `PASS` protected ports unchanged
- `PASS` 18888/18889 unchanged
- `PASS` no foreground route change

## Failures

- none

## Detail

```json
{
  "approval": {
    "operator_approved": true,
    "env_approved": false,
    "approval_file": "F:\\Project\\Digua\\operator_approval\\qwen_systemd_apply_approved.json",
    "approval_file_exists": true,
    "approval_file_valid": true,
    "approval_file_error": null,
    "approval_file_payload": {
      "approved": true,
      "operator": "zhexu",
      "timestamp": "2026-07-04T00:07:25.9449444+08:00",
      "target_unit": "qwen25-local-openai-gateway.service",
      "target_unit_sha256": "d4f3a198305894becde33cc318c24b23ac14a1664dc62d5c89a6102c90b783a0",
      "maintenance_window": "2026-07-04T00:07:25+08:00 immediate operator-approved Stage2.10 maintenance window",
      "rollback_acknowledged": true,
      "approval_source": "user_message: 我批准了，你自己创建批准文件，往下推进",
      "scope": "Apply and verify Qwen local gateway systemd persistence only; no OpenClaw replacement, no Qwen model replacement, no foreground sidecar, no write/destructive/admin/recovery workspace, no private cloud egress."
    },
    "target_unit_sha256": "d4f3a198305894becde33cc318c24b23ac14a1664dc62d5c89a6102c90b783a0"
  },
  "applied": true,
  "restart_ok": true,
  "service_active_enabled": true,
  "owner_before": {
    "pid": 42829,
    "user": "sunrise",
    "cwd": "/mnt/nas/openclaw",
    "cmdline_hash": "2e7323639d059037a825158b9c63736962d01aef10e1f43f02781672df1fb87c",
    "env_hash": "0d8a4a7de62c5e38f5125284ca976efc2dfdc56dd8f9b71ae76d17e656c40cbb",
    "probe": {
      "returncode": 0,
      "elapsed_ms": 229.302,
      "stdout_hash": "cde83b3c1a1e2f658df6edae2ded37031f53c71d344c9e89ac485002d49f60ff",
      "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_tail": "__PS__\n  42829    1622 sunrise  Tue Jun 30 20:17:20 2026 Ss    0.0  0.1 25408 python3         /usr/bin/python3 /mnt/nas/openclaw/scripts/qwen25_openai_gateway.py --config /mnt/nas/openclaw/configs/qwen25_official_route_policy.json\n__CWD__\n/mnt/nas/openclaw\n__CMDLINE__\n/usr/bin/python3 /mnt/nas/openclaw/scripts/qwen25_openai_gateway.py --config /mnt/nas/openclaw/configs/qwen25_official_route_policy.json __ENV_HASH__\n0d8a4a7de62c5e38f5125284ca976efc2dfdc56dd8f9b71ae76d17e656c40cbb  -\n__SYSTEMD__\ninactive\n"
    }
  },
  "unit_sha256": "d4f3a198305894becde33cc318c24b23ac14a1664dc62d5c89a6102c90b783a0",
  "route_policy_sha256": "3d0b3348cc61b96bdaef9f195eee56339ad24f0f5fdcc9d79ab4c507e25db655",
  "gateway_script_sha256": "3c75b901126e8783f0e3e36803b902eb1bef09507c7d4a27931834ba6577081f",
  "before_ports": {
    "ports": [
      8765,
      18080,
      18888,
      18889
    ],
    "stdout": "LISTEN 0      511        127.0.0.1:18765      0.0.0.0:*                                      \nLISTEN 0      5          127.0.0.1:18888      0.0.0.0:*                                      \nLISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=42829,fd=3))\nLISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=42831,fd=3))\nLISTEN 0      511            [::1]:18765         [::]:*                                      \n",
    "stdout_hash": "422810341c68e53763d7c0622c403e9e6f6508f45b9e4c37057bbae81a2e6fdc",
    "returncode": 0
  },
  "after_ports": {
    "ports": [
      8765,
      18080,
      18888,
      18889
    ],
    "stdout": "LISTEN 0      511        127.0.0.1:18765      0.0.0.0:*                                       \nLISTEN 0      5          127.0.0.1:18888      0.0.0.0:*                                       \nLISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=854063,fd=3))\nLISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=42831,fd=3)) \nLISTEN 0      511            [::1]:18765         [::]:*                                       \n",
    "stdout_hash": "4170b1d0f75ae557d7940ef33784686dac6599043a03b2a83cb298f28127b891",
    "returncode": 0
  },
  "qwen_before": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.001129,
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
  },
  "qwen_after": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.001086,
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
  },
  "models_before": {
    "object": "list",
    "data": [
      {
        "id": "Qwen2.5-1.5B-Instruct-S100P-official",
        "object": "model",
        "owned_by": "local-s100p-official-qwen"
      }
    ]
  },
  "models_after": {
    "object": "list",
    "data": [
      {
        "id": "Qwen2.5-1.5B-Instruct-S100P-official",
        "object": "model",
        "owned_by": "local-s100p-official-qwen"
      }
    ]
  },
  "openclaw_before": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.696329,
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
    "stderr_tail": "",
    "endpoint": "/api/health"
  },
  "openclaw_after": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.73511,
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
    "stderr_tail": "",
    "endpoint": "/api/health"
  },
  "apply_result": {
    "returncode": 0,
    "elapsed_ms": 3533.746,
    "stdout_hash": "9960aed9c98725b064e2dceeb2f06fabfa1281da3e2202da6c84b0a358ee2d21",
    "stderr_hash": "767ddecc3b1341ad35bd215a0448a93649bf58e250214332005de63429afd1dc",
    "stdout_tail": "active\nenabled\nactive\nenabled\n",
    "stderr_tail": "Created symlink /etc/systemd/system/multi-user.target.wants/qwen25-local-openai-gateway.service → /etc/systemd/system/qwen25-local-openai-gateway.service.\n"
  },
  "service_state": {
    "returncode": 0,
    "elapsed_ms": 195.303,
    "stdout_hash": "612ef31e41f2c808c1831df8b3ba438325cda9927a51f714b67959559163622c",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "active\nenabled\n"
  },
  "foreground_route_unchanged": true
}
```
