# stage2_s100p_runtime_trace_completeness_gate

- verdict: `ok_stage2_s100p_runtime_trace_completeness_gate`
- generated_at: `2026-07-03T01:38:22.740282+08:00`
- passed: `4/4`

## Checks

- `PASS` trace complete rate >= 0.99
- `PASS` every denied call has reason_code
- `PASS` no raw private args/snippets in trace
- `PASS` sampled traces replayable enough for audit

## Failures

- none

## Detail

```json
{
  "trace_jsonl": "reports/stage2_s100p_live_runtime_trace.jsonl",
  "trace_complete_rate": 1.0,
  "run_count": 20,
  "sampled_runs": [
    {
      "run_id": "nas_search-live-01",
      "workspace_id": "nas_search",
      "user_prompt_hash": "5d993c97b5cfceda79a7b6703c6b9cd7e2887262701e0ce15d1bd373e164b371",
      "context_hash": "a37ea0671b19f2463da74714f7587a02f05536ade841880e968a3e401d8e47e7",
      "model_provider_identity": "Qwen2.5-1.5B-Instruct-S100P-official",
      "exposed_tools": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "hidden_tool_count": 78,
      "tool_calls": [
        {
          "tool_id": "ai_nas_file_search",
          "status": "executed",
          "args_hash": "5d993c97b5cfceda79a7b6703c6b9cd7e2887262701e0ce15d1bd373e164b371"
        }
      ],
      "denied_tool_calls": [],
      "args_hash": "5d993c97b5cfceda79a7b6703c6b9cd7e2887262701e0ce15d1bd373e164b371",
      "dispatcher_sha256": "d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a",
      "redaction_applied": false,
      "cloud_called": false,
      "memory_reads": [],
      "final_response_hash": "3b2bc9a6ac96582fb766116fdf54ed981e7294c892ab4c5b7a3a7271833d254d",
      "status": "executed",
      "raw_private_args_recorded": false
    },
    {
      "run_id": "nas_search-live-02",
      "workspace_id": "nas_search",
      "user_prompt_hash": "619b7992e05c1a5e5deabab813b0fc79c97334a5992aa0e8d36ef1ef989d0a78",
      "context_hash": "3f29b854914a65390d424e3bb9fffb7e7fbd27ad4bcbbfa46151123d624744e4",
      "model_provider_identity": "Qwen2.5-1.5B-Instruct-S100P-official",
      "exposed_tools": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "hidden_tool_count": 78,
      "tool_calls": [
        {
          "tool_id": "ai_nas_permission_aware_search",
          "status": "executed",
          "args_hash": "619b7992e05c1a5e5deabab813b0fc79c97334a5992aa0e8d36ef1ef989d0a78"
        }
      ],
      "denied_tool_calls": [],
      "args_hash": "619b7992e05c1a5e5deabab813b0fc79c97334a5992aa0e8d36ef1ef989d0a78",
      "dispatcher_sha256": "d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a",
      "redaction_applied": true,
      "cloud_called": false,
      "memory_reads": [],
      "final_response_hash": "2db4445468042f68987078703218530795c62ef4a6c6acafdd7635ac5a618eb3",
      "status": "executed",
      "raw_private_args_recorded": false
    },
    {
      "run_id": "nas_search-live-03",
      "workspace_id": "nas_search",
      "user_prompt_hash": "b3684241a7b620f6a4332758809ebc8c3c195d13d22ac8d27b7afb0b3424d217",
      "context_hash": "a37ea0671b19f2463da74714f7587a02f05536ade841880e968a3e401d8e47e7",
      "model_provider_identity": "Qwen2.5-1.5B-Instruct-S100P-official",
      "exposed_tools": [
        "ai_nas_file_search",
        "ai_nas_index_status",
        "ai_nas_permission_aware_search"
      ],
      "hidden_tool_count": 78,
      "tool_calls": [
        {
          "tool_id": "ai_nas_file_search",
          "status": "denied",
          "args_hash": "b3684241a7b620f6a4332758809ebc8c3c195d13d22ac8d27b7afb0b3424d217"
        }
      ],
      "denied_tool_calls": [
        {
          "tool_id": "ai_nas_file_search",
          "reason_code": "absolute_or_private_path_denied"
        }
      ],
      "args_hash": "b3684241a7b620f6a4332758809ebc8c3c195d13d22ac8d27b7afb0b3424d217",
      "dispatcher_sha256": "d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a",
      "redaction_applied": true,
      "cloud_called": false,
      "memory_reads": [],
      "final_response_hash": "d647f90a623a62798a40d73b5c102d7267151e0c0ba0d5f3c54645908e2fc27a",
      "status": "denied",
      "raw_private_args_recorded": false
    },
    {
      "run_id": "document_rag-live-07",
      "workspace_id": "document_rag",
      "user_prompt_hash": "e873e0251962e2ef4fb8acfd42b3cd2ec54f34fda415effd7ea1a7ce0e3155a0",
      "context_hash": "21c86a4f0db4b2cd4921ac339fb9794b809107977c2dd05dfd72a8b497ab48b0",
      "model_provider_identity": "Qwen2.5-1.5B-Instruct-S100P-official",
      "exposed_tools": [
        "ai_nas_evidence_report",
        "ai_nas_folder_rag",
        "ai_nas_folder_summary"
      ],
      "hidden_tool_count": 78,
      "tool_calls": [
        {
          "tool_id": "ai_nas_folder_rag",
          "status": "denied",
          "args_hash": "e873e0251962e2ef4fb8acfd42b3cd2ec54f34fda415effd7ea1a7ce0e3155a0"
        }
      ],
      "denied_tool_calls": [
        {
          "tool_id": "ai_nas_folder_rag",
          "reason_code": "absolute_or_private_path_denied"
        }
      ],
      "args_hash": "e873e0251962e2ef4fb8acfd42b3cd2ec54f34fda415effd7ea1a7ce0e3155a0",
      "dispatcher_sha256": "d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a",
      "redaction_applied": true,
      "cloud_called": false,
      "memory_reads": [],
      "final_response_hash": "e6dfb53adca1c12f0308a084d0f7cd0e2b0870daad4189ba91ad6d3f0abaf5e9",
      "status": "denied",
      "raw_private_args_recorded": false
    },
    {
      "run_id": "document_rag-live-08",
      "workspace_id": "document_rag",
      "user_prompt_hash": "88bc425e1560d5a8a2f5472d4849069c42a3e3edb4827e799d5a2c67e9655006",
      "context_hash": "aff6f5573e9e0a3ae8c7183a0964cceaf9accafd4be08c3b8a5b9e8042d14389",
      "model_provider_identity": "Qwen2.5-1.5B-Instruct-S100P-official",
      "exposed_tools": [
        "ai_nas_evidence_report",
        "ai_nas_folder_rag",
        "ai_nas_folder_summary"
      ],
      "hidden_tool_count": 78,
      "tool_calls": [
        {
          "tool_id": "ai_nas_evidence_report",
          "status": "denied",
          "args_hash": "88bc425e1560d5a8a2f5472d4849069c42a3e3edb4827e799d5a2c67e9655006"
        }
      ],
      "denied_tool_calls": [
        {
          "tool_id": "ai_nas_evidence_report",
          "reason_code": "case_policy_denied"
        }
      ],
      "args_hash": "88bc425e1560d5a8a2f5472d4849069c42a3e3edb4827e799d5a2c67e9655006",
      "dispatcher_sha256": "d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a",
      "redaction_applied": true,
      "cloud_called": false,
      "memory_reads": [],
      "final_response_hash": "e39778a8c0e56969b466e3353c737024a322731a1641632d71ec1fc69b38dd0f",
      "status": "denied",
      "raw_private_args_recorded": false
    }
  ]
}
```
