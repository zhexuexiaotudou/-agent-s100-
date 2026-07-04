# stage3_shadow_tap_integrity_gate

- verdict: `ok_stage3_shadow_tap_integrity_gate`
- generated_at: `2026-07-04T00:38:53.782057+08:00`
- passed: `6/6`

## Checks

- `PASS` shadow tap can be enabled and disabled by env flag
- `PASS` shadow tap trace produced for every seed case
- `PASS` raw private prompt is not stored
- `PASS` foreground response is not modified
- `PASS` sidecar is not foreground route
- `PASS` baseline protected ports are only observed by tap

## Failures

- none

## Detail

```json
{
  "config": {
    "version": "stage3_readonly_shadow_policy_v1",
    "env_flag": "AI_NAS_STAGE3_SHADOW",
    "enabled_value": "1",
    "disabled_value": "0",
    "default_enabled": false,
    "mode": "readonly_shadow_dry_run_policy_first",
    "foreground_route_change_allowed": false,
    "sidecar_foreground_allowed": false,
    "raw_private_prompt_storage_allowed": false,
    "qwen_tool_execution_authority": false,
    "qwen_structured_decision": "disabled",
    "qwen_advisor": "disabled_safe_mode",
    "allowed_workspaces": [
      "nas_search",
      "document_rag"
    ],
    "forbidden_workspaces": [
      "nas_action",
      "ops_recovery",
      "admin_audit",
      "web_cloud_research",
      "dream7b_foreground"
    ],
    "allowed_readonly_tools": [
      "ai_nas_permission_aware_search",
      "ai_nas_file_search",
      "ai_nas_index_status",
      "ai_nas_folder_rag",
      "ai_nas_folder_summary",
      "ai_nas_evidence_report",
      "ai_nas_ocr_readiness",
      "ai_nas_ocr_extract"
    ],
    "dispatcher": "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh",
    "cloud_private_egress_allowed": false,
    "stage4_entry_allowed_by_this_packet": false
  },
  "trace": "reports/stage3_shadow/stage3_shadow_tap_trace.jsonl",
  "summary": {
    "tap_run_count": 12,
    "raw_private_prompt_stored_count": 0,
    "foreground_response_modified_count": 0,
    "private_leak_count": 0,
    "shadow_directory": "reports/stage3_shadow"
  }
}
```
