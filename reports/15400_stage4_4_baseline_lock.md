# stage4_4_baseline_lock

- verdict: `ok_stage4_4_baseline_lock`
- generated_at: `2026-07-04T12:31:21.302373+08:00`
- passed: `7/7`

## Checks

- `PASS` previous real NAS copy candidate packet exists
- `PASS` previous copy candidate passed and target rolled back
- `PASS` S100P identity sampled over SSH
- `PASS` NAS mount sampled
- `PASS` OpenClaw/Qwen health OK
- `PASS` protected ports sampled
- `PASS` allowlisted dispatcher hash recorded

## Failures

- none

## Detail

```json
{
  "previous_final_verdict": "real_nas_copy_candidate_test_passed_target_rolled_back_source_retained",
  "previous_copy_summary": {
    "source_retained": true,
    "target_missing_after_rollback": true,
    "copy_verified": true,
    "rollback_verified": true,
    "source_relative_path": "Collections/CodexPreflight/source/real_nas_copy_candidate_20260704-120353_source.txt",
    "target_relative_path": "Collections/CodexPreflight/target/real_nas_copy_candidate_20260704-120353_copied.txt"
  },
  "remote_identity": {
    "returncode": 0,
    "elapsed_ms": 235.024,
    "stdout_hash": "d7c3a23a0a9814201fdf65bf734f0b281498e259ce80aed833cd0fff0d1ece56",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "__WHOAMI__\nsunrise\n__HOSTNAME__\nubuntu\n__ADDR__\nlo               UNKNOWN        127.0.0.1/8 ::1/128 \neth0             UP             169.254.8.10/16 fe80::6c75:dfff:fe40:9cbc/64 \neth1             UP             192.168.127.10/24 192.168.137.10/24 \ndocker0          DOWN           172.17.0.1/16 \n__NAS__\nTARGET            SOURCE                            FSTYPE OPTIONS\n/mnt/nas/openclaw 169.254.143.37:/OpenClawWorkspace nfs4   rw,relatime,vers=4.1,rsize=1048576,wsize=1048576,namlen=255,hard,proto=tcp,timeo=600,retrans=2,sec=sys,clientaddr=169.254.8.10,local_lock=none,addr=169.254.143.37\n__UNITS__\nactive\nactive\n__PORTS__\nLISTEN 0      5          127.0.0.1:18888      0.0.0.0:*                                       \nLISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=854063,fd=3))\nLISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=42831,fd=3)) \n"
  },
  "remote_identity_stdout_tail": "__WHOAMI__\nsunrise\n__HOSTNAME__\nubuntu\n__ADDR__\nlo               UNKNOWN        127.0.0.1/8 ::1/128 \neth0             UP             169.254.8.10/16 fe80::6c75:dfff:fe40:9cbc/64 \neth1             UP             192.168.127.10/24 192.168.137.10/24 \ndocker0          DOWN           172.17.0.1/16 \n__NAS__\nTARGET            SOURCE                            FSTYPE OPTIONS\n/mnt/nas/openclaw 169.254.143.37:/OpenClawWorkspace nfs4   rw,relatime,vers=4.1,rsize=1048576,wsize=1048576,namlen=255,hard,proto=tcp,timeo=600,retrans=2,sec=sys,clientaddr=169.254.8.10,local_lock=none,addr=169.254.143.37\n__UNITS__\nactive\nactive\n__PORTS__\nLISTEN 0      5          127.0.0.1:18888      0.0.0.0:*                                       \nLISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=854063,fd=3))\nLISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=42831,fd=3)) \n",
  "ports": {
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
  "openclaw": {
    "ok": true,
    "returncode": 0,
    "http_code": "200",
    "time_total": 0.864461,
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
    "time_total": 0.002338,
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
  "dispatcher_hash": "d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a",
  "boundary": [
    "Stage4.4 does not repeat real NAS execute.",
    "Stage4.4 exposes preview/dry-run/confirm contract only.",
    "Execute and rollback routes remain disabled by feature flag."
  ]
}
```
