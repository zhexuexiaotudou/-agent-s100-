# stage2_real_sidecar_resource_rollback_gate

- verdict: `ok_stage2_real_sidecar_resource_rollback_gate`
- generated_at: `2026-07-03T01:38:25.822895+08:00`
- passed: `7/7`

## Checks

- `PASS` sidecar stop command returns zero
- `PASS` no sidecar process remains
- `PASS` OpenClaw health pass after rollback
- `PASS` Qwen health pass after rollback
- `PASS` dispatcher hash unchanged/recorded
- `PASS` zombie process count acceptable
- `PASS` Dream/llama process not touched by stop command

## Failures

- none

## Detail

```json
{
  "before_snapshot": {
    "returncode": 0,
    "elapsed_ms": 562.224,
    "stdout_hash": "c166e9d870e0638610f696bf93991109207640e5dd2f6396657e0fe430114185",
    "stderr_hash": "0c7d4405eb8e99583889e05c63b3e65ca0d4cfba82731ab451bca83cffd893bd",
    "stdout_tail": "at_v11 --output-root . --dtype bfloat16 --torch-threads 6 --report-json reports/1030_1040_v12r_remote_reconstruction.json --report-md reports/1030_1040_v12r_remote_reconstruction.md >> logs/1030_1040_v12r_remote_reconstruction_resume.log 2>&1 < /dev/null &\n 540302  540301 S     0.0  0.0   512 timeout         timeout 54000 python3 -u tools/run_v12r_remote_reconstruction.py --model-dir /mnt/nas/openclaw/models/dream7b-hf --cases /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/canonical_seq128_cases_v10.jsonl --hf-boundary-root /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/hf_boundaries_v11 --bpu-boundary-root evidence/bpu_boundaries_v12r --full-truth-root /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/full_truth_repeat_v11 --output-root . --dtype bfloat16 --torch-threads 6 --report-json reports/1030_1040_v12r_remote_reconstruction.json --report-md reports/1030_1040_v12r_remote_reconstruction.md\n 540303  540302 Rl    117 61.7 13764928 python3      python3 -u tools/run_v12r_remote_reconstruction.py --model-dir /mnt/nas/openclaw/models/dream7b-hf --cases /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/canonical_seq128_cases_v10.jsonl --hf-boundary-root /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/hf_boundaries_v11 --bpu-boundary-root evidence/bpu_boundaries_v12r --full-truth-root /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/full_truth_repeat_v11 --output-root . --dtype bfloat16 --torch-threads 6 --report-json reports/1030_1040_v12r_remote_reconstruction.json --report-md reports/1030_1040_v12r_remote_reconstruction.md\n__LOAD__\n 01:38:06 up 2 days,  8:20,  1 user,  load average: 6.24, 6.65, 6.42\n               total        used        free      shared  buff/cache   available\nMem:           21783        2942        1392          46       17447       18572\nSwap:              0           0           0\n",
    "stderr_tail": "Failed to get unit file state for qwen25-local-openai-gateway.service: No such file or directory\n"
  },
  "during_snapshot": {
    "returncode": 0,
    "elapsed_ms": 413.827,
    "stdout_hash": "ded68666026ca729715e35bd2eeb56202fef9b6df0095762bff3b8641483db84",
    "stderr_hash": "0c7d4405eb8e99583889e05c63b3e65ca0d4cfba82731ab451bca83cffd893bd",
    "stdout_tail": "at_v11 --output-root . --dtype bfloat16 --torch-threads 6 --report-json reports/1030_1040_v12r_remote_reconstruction.json --report-md reports/1030_1040_v12r_remote_reconstruction.md >> logs/1030_1040_v12r_remote_reconstruction_resume.log 2>&1 < /dev/null &\n 540302  540301 S     0.0  0.0   512 timeout         timeout 54000 python3 -u tools/run_v12r_remote_reconstruction.py --model-dir /mnt/nas/openclaw/models/dream7b-hf --cases /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/canonical_seq128_cases_v10.jsonl --hf-boundary-root /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/hf_boundaries_v11 --bpu-boundary-root evidence/bpu_boundaries_v12r --full-truth-root /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/full_truth_repeat_v11 --output-root . --dtype bfloat16 --torch-threads 6 --report-json reports/1030_1040_v12r_remote_reconstruction.json --report-md reports/1030_1040_v12r_remote_reconstruction.md\n 540303  540302 Rl    117 61.7 13764928 python3      python3 -u tools/run_v12r_remote_reconstruction.py --model-dir /mnt/nas/openclaw/models/dream7b-hf --cases /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/canonical_seq128_cases_v10.jsonl --hf-boundary-root /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/hf_boundaries_v11 --bpu-boundary-root evidence/bpu_boundaries_v12r --full-truth-root /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/full_truth_repeat_v11 --output-root . --dtype bfloat16 --torch-threads 6 --report-json reports/1030_1040_v12r_remote_reconstruction.json --report-md reports/1030_1040_v12r_remote_reconstruction.md\n__LOAD__\n 01:38:13 up 2 days,  8:20,  1 user,  load average: 7.06, 6.81, 6.48\n               total        used        free      shared  buff/cache   available\nMem:           21783        2964        1370          46       17448       18551\nSwap:              0           0           0\n",
    "stderr_tail": "Failed to get unit file state for qwen25-local-openai-gateway.service: No such file or directory\n"
  },
  "after_snapshot": {
    "returncode": 0,
    "elapsed_ms": 254.996,
    "stdout_hash": "057079f35ca177bb3d31a88e952848db358dbc4b86af1b828a5a962c660a98cc",
    "stderr_hash": "0c7d4405eb8e99583889e05c63b3e65ca0d4cfba82731ab451bca83cffd893bd",
    "stdout_tail": "at_v11 --output-root . --dtype bfloat16 --torch-threads 6 --report-json reports/1030_1040_v12r_remote_reconstruction.json --report-md reports/1030_1040_v12r_remote_reconstruction.md >> logs/1030_1040_v12r_remote_reconstruction_resume.log 2>&1 < /dev/null &\n 540302  540301 S     0.0  0.0   512 timeout         timeout 54000 python3 -u tools/run_v12r_remote_reconstruction.py --model-dir /mnt/nas/openclaw/models/dream7b-hf --cases /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/canonical_seq128_cases_v10.jsonl --hf-boundary-root /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/hf_boundaries_v11 --bpu-boundary-root evidence/bpu_boundaries_v12r --full-truth-root /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/full_truth_repeat_v11 --output-root . --dtype bfloat16 --torch-threads 6 --report-json reports/1030_1040_v12r_remote_reconstruction.json --report-md reports/1030_1040_v12r_remote_reconstruction.md\n 540303  540302 Rl    117 61.7 13764928 python3      python3 -u tools/run_v12r_remote_reconstruction.py --model-dir /mnt/nas/openclaw/models/dream7b-hf --cases /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/canonical_seq128_cases_v10.jsonl --hf-boundary-root /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/hf_boundaries_v11 --bpu-boundary-root evidence/bpu_boundaries_v12r --full-truth-root /mnt/nas/openclaw/reports/models/dream7b_s100p_v11_execution_20260701/evidence/full_truth_repeat_v11 --output-root . --dtype bfloat16 --torch-threads 6 --report-json reports/1030_1040_v12r_remote_reconstruction.json --report-md reports/1030_1040_v12r_remote_reconstruction.md\n__LOAD__\n 01:38:23 up 2 days,  8:21,  1 user,  load average: 7.50, 6.92, 6.51\n               total        used        free      shared  buff/cache   available\nMem:           21783        2962        1368          46       17452       18553\nSwap:              0           0           0\n",
    "stderr_tail": "Failed to get unit file state for qwen25-local-openai-gateway.service: No such file or directory\n"
  },
  "stop": {
    "returncode": 0,
    "elapsed_ms": 948.883,
    "stdout_hash": "bad0a2f431b20e15dbe63e921904c371e327930513f08b8b387c46839e3b86c1",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "stopped_pid=603077\n"
  },
  "after_openclaw": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.366545,
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
  "after_qwen": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.002158,
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
}
```
