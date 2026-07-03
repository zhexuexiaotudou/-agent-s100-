# stage2_9_baseline_lock

- verdict: `ok_stage2_9_baseline_lock`
- generated_at: `2026-07-03T23:44:09.173767+08:00`
- passed: `8/8`

## Checks

- `PASS` Stage2.8 required evidence files exist
- `PASS` Stage2.8 final verdict blocks only Qwen persistence approval
- `PASS` only Stage3 Go/No-Go false condition is qwen_persistence_applied_and_verified
- `PASS` policy-first contract inherited pass
- `PASS` advisor disabled safe mode inherited
- `PASS` readonly shadow soak inherited pass
- `PASS` current Qwen owner and health sampled
- `PASS` current OpenClaw health and protected ports sampled

## Failures

- none

## Detail

```json
{
  "stage2_8_package": {
    "path": "F:\\Project\\Digua\\evidence_for_gptpro\\digua_ai_nas_harness_stage2_8_for_gptpro_20260703-172337.zip",
    "exists": true,
    "sha256": "7bc82f76a4b1ec565b7396ce3e3fa6c65fa7085d033cb664a587a2c1d0fd8239",
    "packet_package_sha256": "7bc82f76a4b1ec565b7396ce3e3fa6c65fa7085d033cb664a587a2c1d0fd8239"
  },
  "stage2_8_final_verdict": "blocked_by_no_operator_approval_for_qwen_persistence",
  "stage2_8_conditions": {
    "qwen_persistence_applied_and_verified": false,
    "policy_first_contract_pass": true,
    "qwen_advisor_pass_or_disabled_safe": true,
    "readonly_shadow_preflight_soak_pass": true,
    "no_write_destructive_admin_recovery": true,
    "no_production_route_change": true,
    "no_cloud_private_egress": true,
    "rollback_pass": true
  },
  "false_conditions": [
    "qwen_persistence_applied_and_verified"
  ],
  "policy_first_contract_pass": true,
  "advisor_disabled_safe_mode": true,
  "readonly_shadow_soak_pass": true,
  "current_qwen_owner": {
    "pid": 42829,
    "user": "sunrise",
    "cwd": "/mnt/nas/openclaw",
    "cmdline_hash": "2e7323639d059037a825158b9c63736962d01aef10e1f43f02781672df1fb87c",
    "env_hash": "0d8a4a7de62c5e38f5125284ca976efc2dfdc56dd8f9b71ae76d17e656c40cbb",
    "probe": {
      "returncode": 0,
      "elapsed_ms": 225.372,
      "stdout_hash": "cde83b3c1a1e2f658df6edae2ded37031f53c71d344c9e89ac485002d49f60ff",
      "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_tail": "__PS__\n  42829    1622 sunrise  Tue Jun 30 20:17:20 2026 Ss    0.0  0.1 25408 python3         /usr/bin/python3 /mnt/nas/openclaw/scripts/qwen25_openai_gateway.py --config /mnt/nas/openclaw/configs/qwen25_official_route_policy.json\n__CWD__\n/mnt/nas/openclaw\n__CMDLINE__\n/usr/bin/python3 /mnt/nas/openclaw/scripts/qwen25_openai_gateway.py --config /mnt/nas/openclaw/configs/qwen25_official_route_policy.json __ENV_HASH__\n0d8a4a7de62c5e38f5125284ca976efc2dfdc56dd8f9b71ae76d17e656c40cbb  -\n__SYSTEMD__\ninactive\n"
    }
  },
  "current_qwen_health": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.002139,
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
  "current_qwen_models": {
    "object": "list",
    "data": [
      {
        "id": "Qwen2.5-1.5B-Instruct-S100P-official",
        "object": "model",
        "owned_by": "local-s100p-official-qwen"
      }
    ]
  },
  "current_openclaw_health": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.7156,
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
  "current_protected_ports": {
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
  "hard_constraints": [
    "Stage 2.9 clears only the Qwen persistence blocker.",
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
