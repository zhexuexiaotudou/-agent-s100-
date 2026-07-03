# stage2_7_qwen_service_persistence_closure_gate

- verdict: `ok_stage2_7_qwen_service_persistence_closure_gate_candidate_not_applied`
- generated_at: `2026-07-03T12:59:56.110664+08:00`
- passed: `7/7`

## Checks

- `PASS` Qwen health HTTP 200
- `PASS` /v1/models local identity
- `PASS` current Qwen cmdline located
- `PASS` current config hash captured
- `PASS` candidate unit generated
- `PASS` candidate unit matches current script and config
- `PASS` restart policy documented

## Failures

- none

## Detail

```json
{
  "mode": "candidate_ready_but_not_applied",
  "stage3_blocker_removed": false,
  "qwen_persistence_candidate_ready_but_not_applied": true,
  "service_apply_attempted": false,
  "current_owner_pid": 42829,
  "current_cmdline_hash": "0c5dff16e19002b6f931b348ebbc042c1044561bbdfb3f1291c64dc6234e17c7",
  "current_cwd": "/mnt/nas/openclaw",
  "current_user": "sunrise",
  "safe_environment_hash": "7e25fa5ae4d5fa4cd7cd0a6454b0417a72607e8cfcbda4544796e55e1df10a90",
  "config_hash": "3d0b3348cc61b96bdaef9f195eee56339ad24f0f5fdcc9d79ab4c507e25db655",
  "script_hash": "3c75b901126e8783f0e3e36803b902eb1bef09507c7d4a27931834ba6577081f",
  "candidate_unit": "F:\\Project\\Digua\\deployment\\qwen25-local-openai-gateway.service.candidate",
  "candidate_unit_sha256": "d4f3a198305894becde33cc318c24b23ac14a1664dc62d5c89a6102c90b783a0",
  "apply_rollback_plan": "F:\\Project\\Digua\\deployment\\qwen25-local-openai-gateway.apply_rollback.md",
  "probe_hashes": {
    "stdout_hash": "7e25fa5ae4d5fa4cd7cd0a6454b0417a72607e8cfcbda4544796e55e1df10a90",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  },
  "health": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.001036,
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
  "models": {
    "object": "list",
    "data": [
      {
        "id": "Qwen2.5-1.5B-Instruct-S100P-official",
        "object": "model",
        "owned_by": "local-s100p-official-qwen"
      }
    ]
  }
}
```
