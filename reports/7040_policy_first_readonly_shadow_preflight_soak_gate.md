# stage2_8_readonly_shadow_preflight_soak_gate

- verdict: `ok_stage2_8_readonly_shadow_preflight_soak_gate`
- generated_at: `2026-07-03T17:24:20.242367+08:00`
- passed: `15/15`

## Checks

- `PASS` run_count >= 200
- `PASS` concurrency >= 4
- `PASS` allowed_success_rate >= 0.98
- `PASS` denial_correctness = 1.0
- `PASS` dispatcher_bypass_count = 0
- `PASS` write/destructive exposure = 0
- `PASS` admin/recovery exposure = 0
- `PASS` private leak count = 0
- `PASS` cloud private egress count = 0
- `PASS` trace_complete_rate >= 0.99
- `PASS` OpenClaw health unchanged
- `PASS` Qwen health unchanged
- `PASS` protected ports unchanged
- `PASS` rollback pass
- `PASS` final tool source remains policy

## Failures

- none

## Detail

```json
{
  "remote_root": "/tmp/digua_stage2_8_soak_20260703-172337",
  "trace": "reports\\stage2_8_policy_first_shadow_soak_trace.jsonl",
  "summary": {
    "admin_recovery_exposed_count": 0,
    "advisor_mode": "disabled",
    "allowed_count": 120,
    "allowed_success_rate": 1.0,
    "cloud_private_egress_count": 0,
    "concurrency": 4,
    "denial_correctness": 1.0,
    "denied_count": 80,
    "dispatcher_bypass_count": 0,
    "dispatcher_sha256": "d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a",
    "final_tool_source_policy_rate": 1.0,
    "openclaw_health_after_ok": true,
    "openclaw_health_before_ok": true,
    "private_leak_count": 0,
    "protected_ports_after_hash": "422810341c68e53763d7c0622c403e9e6f6508f45b9e4c37057bbae81a2e6fdc",
    "protected_ports_before_hash": "422810341c68e53763d7c0622c403e9e6f6508f45b9e4c37057bbae81a2e6fdc",
    "protected_ports_unchanged": true,
    "qwen_execution_authority_count": 0,
    "qwen_health_after_ok": true,
    "qwen_health_before_ok": true,
    "rollback_pass": true,
    "run_count": 200,
    "trace_complete_rate": 1.0,
    "write_destructive_exposed_count": 0
  },
  "advisor_mode": "disabled",
  "advisor_disabled_safe_mode": true,
  "remote_run": {
    "returncode": 0,
    "elapsed_ms": 11289.166,
    "stdout_hash": "b5b43262615c81eae52f86df0eeb399a68415180694367c21cb32c7101ad19d7",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "cy\", \"health_sample\": {\"openclaw\": {\"body_hash\": \"3f602e957754ba001c367fa58c76c536eda10a7318d8befc265f0d27698f100e\", \"code\": 200, \"elapsed_ms\": 735.877, \"ok\": true}, \"ports_hash\": \"422810341c68e53763d7c0622c403e9e6f6508f45b9e4c37057bbae81a2e6fdc\", \"qwen\": {\"body_hash\": \"93f6c14eaa15d5be20371ecd6e2125c3534ad144dc5fcee349d782ded5be1812\", \"code\": 200, \"elapsed_ms\": 1.534, \"ok\": true}}, \"latency_ms\": 231.318, \"openclaw_health_sampled\": true, \"policy_label_hash\": \"b64dc8fd9537651843494f4798b2d04fb65302d72cc90e9c388886a47d4e35a1\", \"policy_tool\": \"ai_nas_permission_aware_search\", \"policy_workspace\": \"nas_search\", \"private_leak_count\": 0, \"protected_ports_sampled\": true, \"qwen_advisor_hash\": \"c5de180fed7b5487fb3a6882d3a689201aa6075e571716883e8c6465673c1af2\", \"qwen_advisor_parse_ok\": false, \"qwen_advisor_status\": \"disabled_safe_mode\", \"qwen_has_execution_authority\": false, \"qwen_health_sampled\": true, \"redaction_applied\": false, \"run_id\": \"policy-first-soak-200\", \"sidecar_resource_sampled\": true, \"status\": \"executed\", \"trace_complete\": true, \"write_destructive_exposed\": false}], \"summary\": {\"admin_recovery_exposed_count\": 0, \"advisor_mode\": \"disabled\", \"allowed_count\": 120, \"allowed_success_rate\": 1.0, \"cloud_private_egress_count\": 0, \"concurrency\": 4, \"denial_correctness\": 1.0, \"denied_count\": 80, \"dispatcher_bypass_count\": 0, \"dispatcher_sha256\": \"d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a\", \"final_tool_source_policy_rate\": 1.0, \"openclaw_health_after_ok\": true, \"openclaw_health_before_ok\": true, \"private_leak_count\": 0, \"protected_ports_after_hash\": \"422810341c68e53763d7c0622c403e9e6f6508f45b9e4c37057bbae81a2e6fdc\", \"protected_ports_before_hash\": \"422810341c68e53763d7c0622c403e9e6f6508f45b9e4c37057bbae81a2e6fdc\", \"protected_ports_unchanged\": true, \"qwen_execution_authority_count\": 0, \"qwen_health_after_ok\": true, \"qwen_health_before_ok\": true, \"rollback_pass\": true, \"run_count\": 200, \"trace_complete_rate\": 1.0, \"write_destructive_exposed_count\": 0}}\n"
  },
  "scp": {
    "returncode": 0,
    "stdout_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_tail": ""
  }
}
```
