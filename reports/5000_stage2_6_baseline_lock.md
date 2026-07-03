# stage2_6_baseline_lock

- verdict: `ok_stage2_6_baseline_lock`
- generated_at: `2026-07-03T12:24:47.067095+08:00`
- passed: `6/6`

## Checks

- `PASS` Stage 2.5 package exists
- `PASS` Stage 2.5 required files present
- `PASS` Stage 2.5 verdict recorded
- `PASS` Qwen health status recorded
- `PASS` protected port status recorded
- `PASS` Dream/llama process observation recorded

## Failures

- none

## Detail

```json
{
  "stage2_5": {
    "package_path": "F:\\Project\\Digua\\evidence_for_gptpro\\digua_ai_nas_harness_stage2_5_for_gptpro_20260703-114833.zip",
    "package_exists": true,
    "package_sha256": "00154873e25ad8aa316705ae13a9bdcd1229b19c96c24dc00ef8740c8cfbb337",
    "missing_required": [],
    "stage2_5_verdict": "ready_for_more_readonly_sidecar_trials_on_s100p",
    "stage2_5_all_pass": true,
    "stage2_5_stage3_blocked_by_qwen_unit": true,
    "qwen_unit_status": {
      "qwen_stage3_blocker": true,
      "qwen_active_hbm_exists": false,
      "qwen_service_hash": null
    },
    "agent_loop_qwen_ok_counts": {
      "allowed": 12,
      "true": 4,
      "false": 8,
      "none": 0
    },
    "dispatcher_soak_counts": {
      "denied": 12,
      "executed": 48
    },
    "stage2_5_sidecar_ports": {
      "agent_loop": 19082,
      "soak": 19083
    },
    "stage2_5_soak_summary": {
      "run_count": 60,
      "concurrency": 4,
      "allowed_success_rate": 1.0,
      "denial_correctness": 1.0,
      "leak_count": 0,
      "dispatcher_latency_ms": {
        "p50": 154.749,
        "p95": 730.647,
        "p99": 742.903
      },
      "qwen_health_ms_before": {
        "p50": 1.395,
        "p95": 3.866,
        "p99": 3.866
      },
      "qwen_health_ms_after": {
        "p50": 1.223,
        "p95": 1.404,
        "p99": 1.404
      },
      "openclaw_health_ms_before": {
        "p50": 362.962,
        "p95": 383.454,
        "p99": 383.454
      },
      "openclaw_health_ms_after": {
        "p50": 364.611,
        "p95": 372.781,
        "p99": 372.781
      },
      "status_counts": {
        "denied": 12,
        "executed": 48
      },
      "nonzero_by_tool": {}
    }
  },
  "stage3_still_blocked_reason": "Stage 2.5 marked qwen_stage3_blocker while qwen25-local-openai-gateway.service was missing; Stage 2.6 must re-check persistence and Qwen semantic success.",
  "current_qwen_health": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.001081,
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
  "protected_port_status": {
    "ports": [
      8765,
      18080,
      18888,
      18889,
      19084,
      19085
    ],
    "stdout": "LISTEN 0      511        127.0.0.1:18765      0.0.0.0:*                                      \nLISTEN 0      5          127.0.0.1:18888      0.0.0.0:*                                      \nLISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=42829,fd=3))\nLISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=42831,fd=3))\nLISTEN 0      511            [::1]:18765         [::]:*                                      \n",
    "stdout_hash": "422810341c68e53763d7c0622c403e9e6f6508f45b9e4c37057bbae81a2e6fdc",
    "returncode": 0
  },
  "dream_llama_process_observation": [
    {
      "pid": 41889,
      "ppid": 1613,
      "pcpu": 0.0,
      "pmem": 0.0,
      "rss_kb": 17664,
      "comm": "python",
      "args_hash_source_len": 126
    },
    {
      "pid": 697792,
      "ppid": 1,
      "pcpu": 0.0,
      "pmem": 0.0,
      "rss_kb": 640,
      "comm": "bash",
      "args_hash_source_len": 882
    },
    {
      "pid": 697793,
      "ppid": 697792,
      "pcpu": 0.0,
      "pmem": 0.0,
      "rss_kb": 512,
      "comm": "timeout",
      "args_hash_source_len": 616
    },
    {
      "pid": 697794,
      "ppid": 697793,
      "pcpu": 115.0,
      "pmem": 57.5,
      "rss_kb": 12841216,
      "comm": "python3",
      "args_hash_source_len": 602
    }
  ],
  "remaining_hard_constraints": [
    "Do not replace OpenClaw.",
    "Do not replace local Qwen.",
    "Do not bypass ai_nas_allowlisted_tool.sh.",
    "Do not execute arbitrary shell/script paths.",
    "Do not modify ports 8765/18080/18888/18889.",
    "Do not connect Dream7B to foreground traffic.",
    "Do not stop or modify Dream/llama research processes unless explicitly authorized.",
    "Do not enable write/destructive/admin/recovery workspaces.",
    "Do not allow cloud to see private NAS raw content.",
    "Do not introduce PostgreSQL/pgvector as a production dependency.",
    "Do not use real Zleap as a production dependency."
  ]
}
```
