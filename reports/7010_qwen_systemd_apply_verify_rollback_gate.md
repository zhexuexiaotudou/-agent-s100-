# stage2_8_qwen_systemd_apply_verify_rollback_gate

- verdict: `blocked_by_no_operator_approval`
- generated_at: `2026-07-03T17:23:46.251937+08:00`
- passed: `12/13`

## Checks

- `PASS` candidate unit exists and hash recorded
- `PASS` rollback/apply plan exists
- `PASS` current 18080 service owner confirmed
- `PASS` Qwen health and models OK before apply decision
- `PASS` OpenClaw health OK before apply decision
- `PASS` route policy config hash recorded
- `PASS` gateway script hash recorded
- `FAIL` operator approved
- `PASS` no apply command executed without approval
- `PASS` protected ports unchanged
- `PASS` Qwen health/models OK after gate
- `PASS` OpenClaw health unchanged
- `PASS` rollback plan dry-run verified

## Failures

- `operator approved`

## Detail

```json
{
  "operator_approved": false,
  "approval": {
    "env": false,
    "file_path": "F:\\Project\\Digua\\operator_approval\\qwen_systemd_apply_approved.json",
    "file_valid": false,
    "file_error": "missing",
    "file_payload": null
  },
  "applied": false,
  "restart_ok": false,
  "dry_run_only": true,
  "stage3_blocked": true,
  "current_18080_owner": {
    "pid": 42829,
    "probe": {
      "returncode": 0,
      "elapsed_ms": 397.979,
      "stdout_hash": "339d220bc9ae5dcfe799e65e59b602f1db8944b48200e4fc8bb6fc791ed5c757",
      "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_tail": "__PS__\n  42829    1622 sunrise  Tue Jun 30 20:17:20 2026 Ss    0.0  0.1 25344 python3         /usr/bin/python3 /mnt/nas/openclaw/scripts/qwen25_openai_gateway.py --config /mnt/nas/openclaw/configs/qwen25_official_route_policy.json\n__CWD__\n/mnt/nas/openclaw\n__CMDLINE__\n/usr/bin/python3 /mnt/nas/openclaw/scripts/qwen25_openai_gateway.py --config /mnt/nas/openclaw/configs/qwen25_official_route_policy.json __ENV_HASH__\n0d8a4a7de62c5e38f5125284ca976efc2dfdc56dd8f9b71ae76d17e656c40cbb  -\n__SYSTEMD_STATUS__\ninactive\n"
    }
  },
  "unit_candidate": {
    "path": "F:\\Project\\Digua\\deployment\\qwen25-local-openai-gateway.service.candidate",
    "sha256": "d4f3a198305894becde33cc318c24b23ac14a1664dc62d5c89a6102c90b783a0"
  },
  "route_policy_hash": "3d0b3348cc61b96bdaef9f195eee56339ad24f0f5fdcc9d79ab4c507e25db655",
  "gateway_script_hash": "3c75b901126e8783f0e3e36803b902eb1bef09507c7d4a27931834ba6577081f",
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
    "stdout": "LISTEN 0      511        127.0.0.1:18765      0.0.0.0:*                                      \nLISTEN 0      5          127.0.0.1:18888      0.0.0.0:*                                      \nLISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=42829,fd=3))\nLISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=42831,fd=3))\nLISTEN 0      511            [::1]:18765         [::]:*                                      \n",
    "stdout_hash": "422810341c68e53763d7c0622c403e9e6f6508f45b9e4c37057bbae81a2e6fdc",
    "returncode": 0
  },
  "qwen_health_before": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.001127,
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
  "qwen_health_after": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.001193,
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
  "openclaw_before": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.756708,
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
  "openclaw_after": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.712583,
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
  "apply_result": null,
  "rollback_plan_verified": true
}
```
