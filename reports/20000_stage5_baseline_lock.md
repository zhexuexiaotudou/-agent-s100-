# stage5_baseline_lock

- verdict: `ok_stage5_baseline_lock`
- generated_at: `2026-07-04T14:35:38.987984+08:00`
- passed: `8/8`

## Checks

- `PASS` Stage4.5 packet readable
- `PASS` Stage4.5 execute and rollback passed
- `PASS` Stage4.5 target rolled back and source retained
- `PASS` Stage4.5 feature flags closed after test
- `PASS` OpenClaw/Qwen health OK
- `PASS` protected ports sampled
- `PASS` allowlisted dispatcher hash recorded
- `PASS` Qwen execution authority false in previous packet

## Failures

- none

## Detail

```json
{
  "stage4_5_final_verdict": "self_created_synthetic_route_copy_canary_passed_target_rolled_back",
  "stage4_5_reports": {
    "15560_stage4_5_route_execute_canary_gate.json": "ok_stage4_5_route_execute_canary_gate",
    "15570_stage4_5_route_rollback_canary_gate.json": "ok_stage4_5_route_rollback_canary_gate",
    "15580_stage4_5_feature_flag_close_and_health_gate.json": "ok_stage4_5_feature_flag_close_and_health_gate",
    "15590_stage4_5_post_execute_adversarial_regression_gate.json": "ok_stage4_5_post_execute_adversarial_regression_gate",
    "15600_stage4_5_readonly_regression_mini_soak_gate.json": "ok_stage4_5_readonly_regression_mini_soak_gate"
  },
  "service_state": {
    "returncode": 0,
    "elapsed_ms": 197.264,
    "stdout_hash": "e4e5bbc88e8106a3b65e8c5ff6d8e9b20ce0d718f94506e99282a0d5166b851f",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "sunrise\nubuntu\nTARGET            SOURCE                            FSTYPE OPTIONS\n/mnt/nas/openclaw 169.254.143.37:/OpenClawWorkspace nfs4   rw,relatime,vers=4.1,rsize=1048576,wsize=1048576,namlen=255,hard,proto=tcp,timeo=600,retrans=2,sec=sys,clientaddr=169.254.8.10,local_lock=none,addr=169.254.143.37\nactive\nactive\n"
  },
  "service_state_stdout_tail": "sunrise\nubuntu\nTARGET            SOURCE                            FSTYPE OPTIONS\n/mnt/nas/openclaw 169.254.143.37:/OpenClawWorkspace nfs4   rw,relatime,vers=4.1,rsize=1048576,wsize=1048576,namlen=255,hard,proto=tcp,timeo=600,retrans=2,sec=sys,clientaddr=169.254.8.10,local_lock=none,addr=169.254.143.37\nactive\nactive\n",
  "openclaw": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.878279,
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
    "time_total": 0.002231,
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
  "protected_ports": {
    "ports": [
      8765,
      18080,
      18888,
      18889
    ],
    "stdout": "LISTEN 0      511        127.0.0.1:18765      0.0.0.0:*                                        \nLISTEN 0      5          127.0.0.1:18888      0.0.0.0:*                                        \nLISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=1028631,fd=3))\nLISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=1031214,fd=3))\nLISTEN 0      511            [::1]:18765         [::]:*                                        \n",
    "stdout_hash": "e0c13087cda407b8904557d146cf1ba9f2221f34cb5b75a52933d2cacf990d55",
    "returncode": 0
  },
  "normalized_protected_ports": [
    "LISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=<pid>,fd=3))",
    "LISTEN 0      5          127.0.0.1:18888      0.0.0.0:*",
    "LISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=<pid>,fd=3))"
  ],
  "dispatcher_hash": "d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a",
  "forbidden_actions": [
    "delete",
    "move",
    "rename",
    "chmod",
    "chown",
    "overwrite",
    "recursive",
    "recursive_delete",
    "arbitrary_shell"
  ]
}
```
