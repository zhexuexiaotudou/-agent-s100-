# stage2_8_policy_first_shadow_contract_gate

- verdict: `ok_stage2_8_policy_first_shadow_contract_gate`
- generated_at: `2026-07-03T17:23:46.257278+08:00`
- passed: `11/11`

## Checks

- `PASS` policy-first architecture document written
- `PASS` Qwen output does not directly decide tool execution
- `PASS` final workspace/tool source is deterministic policy
- `PASS` dispatcher remains sole execution path
- `PASS` Qwen advisory may be empty or failed without privilege escalation
- `PASS` qwen_has_execution_authority=false
- `PASS` final_tool_source=policy
- `PASS` no write/destructive/admin/recovery tools in readonly Stage3 set
- `PASS` Cloud private egress disabled for Stage3 private content
- `PASS` Dream7B foreground disabled
- `PASS` allowed readonly workspace args are read-only

## Failures

- none

## Detail

```json
{
  "architecture": "policy_first_deterministic_router_with_qwen_summarizer_advisor",
  "doc": "F:\\Project\\Digua\\docs\\STAGE3_POLICY_FIRST_ARCHITECTURE.md",
  "allowed_stage3_readonly_workspaces": [
    "document_rag",
    "nas_search"
  ],
  "disabled_stage3_workspaces": [
    "admin_audit",
    "nas_action",
    "ops_recovery",
    "web_cloud_research"
  ],
  "exposed_readonly_tools": {
    "document_rag": [
      "ai_nas_case_packet",
      "ai_nas_evidence_report",
      "ai_nas_folder_rag",
      "ai_nas_folder_rag_grounding_contract",
      "ai_nas_folder_summary",
      "ai_nas_ocr_readiness",
      "ai_nas_ocr_extract",
      "ai_nas_ocr_runtime_contract",
      "ai_nas_document_pipeline_acceptance"
    ],
    "nas_search": [
      "ai_nas_personal_inventory",
      "ai_nas_index_status",
      "ai_nas_permission_aware_search",
      "ai_nas_file_search",
      "ai_nas_search_evidence_contract",
      "ai_nas_search_confidence_calibration_contract",
      "ai_nas_embedding_search",
      "ai_nas_semantic_query_acceptance",
      "ai_nas_folder_summary"
    ]
  },
  "trace_schema": [
    {
      "workspace": "nas_search",
      "policy_decision": {
        "workspace": "nas_search",
        "tool_id": "ai_nas_file_search",
        "source": "deterministic_policy"
      },
      "qwen_advisory": {
        "status": "optional",
        "may_fail": true,
        "may_override_policy": false
      },
      "final_tool_source": "policy",
      "qwen_has_execution_authority": false,
      "execution_path": "ai_nas_allowlisted_tool.sh"
    },
    {
      "workspace": "document_rag",
      "policy_decision": {
        "workspace": "document_rag",
        "tool_id": "ai_nas_folder_rag",
        "source": "deterministic_policy"
      },
      "qwen_advisory": {
        "status": "optional",
        "may_fail": true,
        "may_override_policy": false
      },
      "final_tool_source": "policy",
      "qwen_has_execution_authority": false,
      "execution_path": "ai_nas_allowlisted_tool.sh"
    }
  ]
}
```
