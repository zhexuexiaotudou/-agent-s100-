# stage4_5_feature_flag_close_and_health_gate

- verdict: `ok_stage4_5_feature_flag_close_and_health_gate`
- generated_at: `2026-07-04T13:57:42.094497+08:00`
- passed: `7/7`

## Checks

- `PASS` global config flags still closed after canary
- `PASS` scoped canary flags closed in gate state
- `PASS` closed flags block execute and rollback routes
- `PASS` OpenClaw/Qwen health OK after close
- `PASS` protected ports unchanged after normalization
- `PASS` dispatcher hash unchanged
- `PASS` target remains absent and synthetic source retained

## Failures

- none

## Detail

```json
{
  "global_feature_flags_after": {
    "preview_enabled": true,
    "dry_run_enabled": true,
    "confirm_enabled": true,
    "execute_enabled": false,
    "rollback_enabled": false,
    "execute_canary_enabled": false,
    "require_operator_approval_file": true,
    "require_execute_env": true
  },
  "scoped_flags_after_close": {
    "preview_enabled": true,
    "dry_run_enabled": true,
    "confirm_enabled": true,
    "execute_enabled": false,
    "rollback_enabled": false,
    "execute_canary_enabled": false,
    "require_operator_approval_file": true,
    "require_execute_env": true
  },
  "closed_execute_decision": {
    "allowed": false,
    "route": "execute",
    "status": "execute_blocked",
    "reason_codes": [
      "execute_feature_disabled"
    ],
    "response": {
      "route": "execute",
      "status": "execute_blocked",
      "action_type": "copy",
      "candidate_fingerprint": "9845850926bccef5ba5aeb9b9d39ada668e9a4a7821958e727f97f6e0d6b62c7",
      "source_path_hash": "c3f8de23135918ad682a2e22e1d7e8fabc4f062c48b1e0d6cc9fe17e4eca89b8",
      "target_path_hash": "bb91fbd04ec4d493fb5ffec67a573bda42fbe61dec72c668b146865f86835cf2",
      "source_sha256_prefix": "7c17e4552a22",
      "expected_size_bytes": 199,
      "target_root": "Collections",
      "raw_paths_in_response": false,
      "private_content_in_response": false,
      "dispatcher_tool": "ai_nas_action_execute_copy",
      "execution_performed_by_guard": false,
      "writes_performed": false,
      "blocked_safely": true
    },
    "audit_event": {
      "event_id": "copy-route-18969b56454d40ed",
      "tool_id": "ai_nas_route_copy_guard_v1",
      "route": "execute",
      "allowed": false,
      "reason_codes": [
        "execute_feature_disabled"
      ],
      "candidate_fingerprint": "9845850926bccef5ba5aeb9b9d39ada668e9a4a7821958e727f97f6e0d6b62c7",
      "source_path_hash": "c3f8de23135918ad682a2e22e1d7e8fabc4f062c48b1e0d6cc9fe17e4eca89b8",
      "target_path_hash": "bb91fbd04ec4d493fb5ffec67a573bda42fbe61dec72c668b146865f86835cf2",
      "args_hash": "efbd843bbaca4b4b67fe633768930c8a07e177a652d084af38764dc974d3ec31",
      "qwen_execution_authority": false,
      "cloud_private_egress": false,
      "raw_private_content_logged": false,
      "dispatcher_tool": "ai_nas_action_execute_copy",
      "execution_performed_by_guard": false,
      "operator_approved": true,
      "env_enabled": true,
      "approval_file_present": true,
      "token_validation_reason": "approval_token_ok"
    }
  },
  "closed_rollback_decision": {
    "allowed": false,
    "route": "rollback",
    "status": "rollback_blocked",
    "reason_codes": [
      "rollback_feature_disabled"
    ],
    "response": {
      "route": "rollback",
      "status": "rollback_blocked",
      "action_type": "copy",
      "candidate_fingerprint": "9845850926bccef5ba5aeb9b9d39ada668e9a4a7821958e727f97f6e0d6b62c7",
      "source_path_hash": "c3f8de23135918ad682a2e22e1d7e8fabc4f062c48b1e0d6cc9fe17e4eca89b8",
      "target_path_hash": "bb91fbd04ec4d493fb5ffec67a573bda42fbe61dec72c668b146865f86835cf2",
      "source_sha256_prefix": "7c17e4552a22",
      "expected_size_bytes": 199,
      "target_root": "Collections",
      "raw_paths_in_response": false,
      "private_content_in_response": false,
      "dispatcher_tool": "ai_nas_action_rollback_copy",
      "rollback_performed_by_guard": false,
      "writes_performed": false,
      "blocked_safely": true
    },
    "audit_event": {
      "event_id": "copy-route-2ce2702bc0d14a17",
      "tool_id": "ai_nas_route_copy_guard_v1",
      "route": "rollback",
      "allowed": false,
      "reason_codes": [
        "rollback_feature_disabled"
      ],
      "candidate_fingerprint": "9845850926bccef5ba5aeb9b9d39ada668e9a4a7821958e727f97f6e0d6b62c7",
      "source_path_hash": "c3f8de23135918ad682a2e22e1d7e8fabc4f062c48b1e0d6cc9fe17e4eca89b8",
      "target_path_hash": "bb91fbd04ec4d493fb5ffec67a573bda42fbe61dec72c668b146865f86835cf2",
      "args_hash": "efbd843bbaca4b4b67fe633768930c8a07e177a652d084af38764dc974d3ec31",
      "qwen_execution_authority": false,
      "cloud_private_egress": false,
      "raw_private_content_logged": false,
      "dispatcher_tool": "ai_nas_action_rollback_copy",
      "rollback_performed_by_guard": false,
      "operator_approved": true
    }
  },
  "health": {
    "openclaw": {
      "ok": true,
      "returncode": 0,
      "http_code": "200",
      "time_total": 0.721209,
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
      "time_total": 0.001072,
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
  },
  "ports_after": {
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
  "normalized_ports_after": [
    "LISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=<pid>,fd=3))",
    "LISTEN 0      5          127.0.0.1:18888      0.0.0.0:*",
    "LISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=<pid>,fd=3))"
  ],
  "dispatcher_hash_after": "d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a"
}
```
