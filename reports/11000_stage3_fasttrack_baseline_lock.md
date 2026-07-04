# stage3_fasttrack_baseline_lock

- verdict: `ok_stage3_fasttrack_baseline_lock`
- generated_at: `2026-07-04T00:38:53.779534+08:00`
- passed: `9/9`

## Checks

- `PASS` Stage2.10 required evidence readable
- `PASS` Stage2.10 final verdict allows Stage3 readonly shadow
- `PASS` Stage2.10 shadow trace complete enough
- `PASS` Qwen service active/enabled
- `PASS` OpenClaw health OK
- `PASS` Qwen health and model identity OK
- `PASS` protected ports sampled
- `PASS` dispatcher path/hash recorded
- `PASS` Stage3 policy-first no Qwen execution authority

## Failures

- none

## Detail

```json
{
  "stage2_10_package": {
    "path": "F:\\Project\\Digua\\evidence_for_gptpro\\digua_ai_nas_harness_stage2_10_for_gptpro_20260704-001631.zip",
    "exists": true,
    "sha256": "eb8d3af92b30bd3197693aec8f2093968bb0295a5241c0be67ac19a41a85705f",
    "expected_sha256": "eb8d3af92b30bd3197693aec8f2093968bb0295a5241c0be67ac19a41a85705f"
  },
  "stage2_10_final_verdict": "ready_for_stage3_readonly_shadow_dryrun_policy_first",
  "stage2_10_trace_lines": 200,
  "qwen_service": {
    "active_enabled": true,
    "systemd_lines": [
      "active",
      "enabled",
      "active",
      "enabled"
    ],
    "probe": {
      "returncode": 0,
      "elapsed_ms": 221.899,
      "stdout_hash": "9960aed9c98725b064e2dceeb2f06fabfa1281da3e2202da6c84b0a358ee2d21",
      "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "stdout_tail": "active\nenabled\nactive\nenabled\n"
    }
  },
  "qwen_model_identity": "Qwen2.5-1.5B-Instruct-S100P-official",
  "qwen_health": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.001989,
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
  "qwen_models": {
    "object": "list",
    "data": [
      {
        "id": "Qwen2.5-1.5B-Instruct-S100P-official",
        "object": "model",
        "owned_by": "local-s100p-official-qwen"
      }
    ]
  },
  "openclaw_health": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.729455,
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
  "protected_ports": {
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
  "policy_first_contract": {
    "qwen_has_execution_authority": false,
    "final_tool_source": "policy",
    "allowed_stage3_workspaces": [
      "nas_search",
      "document_rag"
    ],
    "forbidden_stage3_workspaces": [
      "nas_action",
      "ops_recovery",
      "admin_audit",
      "web_cloud_research",
      "dream7b_foreground"
    ],
    "dispatcher_path": "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh",
    "dispatcher_sha256": "d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a"
  },
  "forbidden_stage3_scope": [
    "Do not replace OpenClaw.",
    "Do not replace Qwen.",
    "Do not modify 8765, 18080, 18888, or 18889.",
    "Do not let sidecar or harness become the OpenClaw foreground route.",
    "Do not expose write, destructive, admin, or recovery workspaces.",
    "Do not allow Qwen tool execution authority.",
    "Keep Qwen structured decision disabled.",
    "Keep Qwen advisor disabled_safe_mode unless a separate gate proves it safe.",
    "All real tool calls must go through ai_nas_allowlisted_tool.sh.",
    "Do not let cloud see private NAS raw content.",
    "Do not attach Dream7B foreground.",
    "Do not introduce PostgreSQL or pgvector as a default production dependency.",
    "Do not claim readonly shadow pass is production write readiness.",
    "Do not enter Stage 4."
  ],
  "stage3_shadow_only_claim_boundary": "Stage3 can only produce readonly shadow evidence and cannot claim production write readiness.",
  "stage3_policy_config": "config/stage3_readonly_shadow_policy.json"
}
```
