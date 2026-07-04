# stage3_shadow_rollback_gate

- verdict: `ok_stage3_shadow_rollback_gate`
- generated_at: `2026-07-04T00:39:26.191438+08:00`
- passed: `9/9`

## Checks

- `PASS` rollback_command_success = true
- `PASS` shadow_disabled = true
- `PASS` OpenClaw/Qwen health OK
- `PASS` Qwen service active/enabled
- `PASS` protected ports unchanged
- `PASS` foreground route unchanged
- `PASS` dispatcher hash unchanged
- `PASS` no zombie process
- `PASS` trace finalized

## Failures

- none

## Detail

```json
{
  "probe": {
    "returncode": 0,
    "elapsed_ms": 954.098,
    "stdout_hash": "2e686736e0d87f09be1d1994414f7bdd7f9e96cb4c193a02d52996d79aabc59f",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "__SHADOW_ENV__\n__SHADOW_PROCESS__\n__QWEN_SYSTEMD__\nactive\nenabled\n__HEALTH__\nopenclaw_ok\nqwen_ok\n__PORTS__\nLISTEN 0      511        127.0.0.1:18765      0.0.0.0:*                                       \nLISTEN 0      5          127.0.0.1:18888      0.0.0.0:*                                       \nLISTEN 0      5          127.0.0.1:18080      0.0.0.0:*    users:((\"python3\",pid=854063,fd=3))\nLISTEN 0      5          127.0.0.1:8765       0.0.0.0:*    users:((\"python3\",pid=42831,fd=3)) \nLISTEN 0      511            [::1]:18765         [::]:*                                       \n__DISPATCHER__\nd099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a  /mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh\n"
  },
  "shadow_process_stopped": true,
  "health_ok": true,
  "qwen_active_enabled": true,
  "ports_unchanged": true,
  "dispatcher_unchanged": true,
  "trace_finalized": true
}
```
