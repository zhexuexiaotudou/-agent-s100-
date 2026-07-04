# stage2_10_baseline_lock

- verdict: `ok_stage2_10_baseline_lock`
- generated_at: `2026-07-04T00:07:58.818924+08:00`
- passed: `8/8`

## Checks

- `PASS` Stage2.9 required evidence files exist
- `PASS` Stage2.9 final verdict recorded
- `PASS` current blocker includes operator approval and persistence apply
- `PASS` protected ports sampled
- `PASS` Qwen owner before apply sampled
- `PASS` OpenClaw health before apply OK
- `PASS` Qwen health/models before apply OK
- `PASS` operator approval status recorded

## Failures

- none

## Detail

```json
{
  "stage2_9_package": {
    "path": "F:\\Project\\Digua\\evidence_for_gptpro\\digua_ai_nas_harness_stage2_9_for_gptpro_20260703-234407.zip",
    "exists": true,
    "sha256": "a0a03be1637601ff3e4b5f2d09ebb9a41b21572129fdd8ff92ec295546d0d5dd",
    "packet_package_sha256": "a0a03be1637601ff3e4b5f2d09ebb9a41b21572129fdd8ff92ec295546d0d5dd"
  },
  "stage2_9_final_verdict": "blocked_by_no_operator_approval_for_qwen_persistence",
  "current_blocker": [
    "operator_approved",
    "qwen_persistence_applied_and_verified",
    "service_active_enabled",
    "restart_ok",
    "post_persistence_soak_pass",
    "openclaw_qwen_health_pass"
  ],
  "protected_ports": {
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
  "qwen_owner_before_apply": {
    "pid": 42829,
    "user": "sunrise",
    "cwd": "/mnt/nas/openclaw",
    "cmdline_hash": "2e7323639d059037a825158b9c63736962d01aef10e1f43f02781672df1fb87c",
    "env_hash": "0d8a4a7de62c5e38f5125284ca976efc2dfdc56dd8f9b71ae76d17e656c40cbb",
    "probe": {
      "returncode": 0,
      "elapsed_ms": 229.813,
      "stdout_hash": "cde83b3c1a1e2f658df6edae2ded37031f53c71d344c9e89ac485002d49f60ff",
      "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_tail": "__PS__\n  42829    1622 sunrise  Tue Jun 30 20:17:20 2026 Ss    0.0  0.1 25408 python3         /usr/bin/python3 /mnt/nas/openclaw/scripts/qwen25_openai_gateway.py --config /mnt/nas/openclaw/configs/qwen25_official_route_policy.json\n__CWD__\n/mnt/nas/openclaw\n__CMDLINE__\n/usr/bin/python3 /mnt/nas/openclaw/scripts/qwen25_openai_gateway.py --config /mnt/nas/openclaw/configs/qwen25_official_route_policy.json __ENV_HASH__\n0d8a4a7de62c5e38f5125284ca976efc2dfdc56dd8f9b71ae76d17e656c40cbb  -\n__SYSTEMD__\ninactive\n"
    }
  },
  "openclaw_health_before_apply": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.89834,
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
  "qwen_health_before_apply": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.0021,
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
  "qwen_models_before_apply": {
    "object": "list",
    "data": [
      {
        "id": "Qwen2.5-1.5B-Instruct-S100P-official",
        "object": "model",
        "owned_by": "local-s100p-official-qwen"
      }
    ]
  },
  "operator_approval_status": {
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
  "hard_constraints": [
    "Stage 2.10 is only operator-approved Qwen persistence closure.",
    "Do not replace OpenClaw.",
    "Do not replace the Qwen model.",
    "Do not bypass ai_nas_allowlisted_tool.sh.",
    "Do not execute arbitrary shell/script paths.",
    "Do not modify 8765/18888/18889.",
    "Do not attach sidecar to OpenClaw foreground.",
    "Do not attach Dream7B to foreground.",
    "Do not enable write/destructive/admin/recovery workspaces.",
    "Do not allow cloud to see private NAS raw content.",
    "Do not claim Qwen-driven autonomous agent loop.",
    "Do not call failed Qwen advisor ready.",
    "Do not apply systemd without explicit operator approval."
  ]
}
```
