# stage2_qwen_openclaw_service_persistence_gate

- verdict: `ok_stage2_qwen_openclaw_service_persistence_gate`
- generated_at: `2026-07-03T11:48:45.939711+08:00`
- passed: `5/5`

## Checks

- `PASS` OpenClaw unit present enabled and healthy
- `PASS` Qwen live health recorded
- `PASS` Qwen unit status recorded or Stage3 blocker marked
- `PASS` service hashes recorded
- `PASS` protected routes unchanged after checks

## Failures

- none

## Detail

```json
{
  "systemctl_output_hash": "7f5c6cb4f5befb7180c401468715ff2aca8feadb3c8ec4a4aab6f22ff0164b62",
  "systemctl_stderr_hash": "4685a43df6b6f58dd13e06c4d2b4cc0244b794df386afe069e832582447c570d",
  "systemctl_returncode": 0,
  "hashes": {
    "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh": "d099f8071ab3710778520bf610ce2bca07fbc7976effe0a6d99791cf42ebb23a",
    "/etc/systemd/system/openclaw-gateway.service": "06e3e3d3d1245454676c31033107f25cb71aeae60205c42f8b61d05a30386ccc",
    "/etc/systemd/system/qwen25-local-openai-gateway.service": null
  },
  "qwen_stage3_blocker": true,
  "qwen_active_hbm_exists": false,
  "restart_attempted": false,
  "restart_not_attempted_reason": "No explicit restart authorization; read-only validation only."
}
```
