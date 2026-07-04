# stage2_10_operator_approval_hard_gate

- verdict: `ok_stage2_10_operator_approval_hard_gate`
- generated_at: `2026-07-04T00:07:58.820268+08:00`
- passed: `3/3`

## Checks

- `PASS` target unit sha256 recorded
- `PASS` operator approval pass
- `PASS` apply not executed by hard gate

## Failures

- none

## Detail

```json
{
  "approval": {
    "operator_approved": true,
    "env_approved": false,
    "approval_file": "F:\\Project\\Digua\\operator_approval\\qwen_systemd_apply_approved.json",
    "approval_file_exists": true,
    "approval_file_valid": true,
    "approval_file_error": null,
    "approval_file_payload": {
      "approved": true,
      "operator": "zhexu",
      "timestamp": "2026-07-04T00:07:25.9449444+08:00",
      "target_unit": "qwen25-local-openai-gateway.service",
      "target_unit_sha256": "d4f3a198305894becde33cc318c24b23ac14a1664dc62d5c89a6102c90b783a0",
      "maintenance_window": "2026-07-04T00:07:25+08:00 immediate operator-approved Stage2.10 maintenance window",
      "rollback_acknowledged": true,
      "approval_source": "user_message: 我批准了，你自己创建批准文件，往下推进",
      "scope": "Apply and verify Qwen local gateway systemd persistence only; no OpenClaw replacement, no Qwen model replacement, no foreground sidecar, no write/destructive/admin/recovery workspace, no private cloud egress."
    },
    "target_unit_sha256": "d4f3a198305894becde33cc318c24b23ac14a1664dc62d5c89a6102c90b783a0"
  },
  "manual_action_if_blocked": [
    "Review deployment/qwen25-local-openai-gateway.service.candidate.",
    "Use a maintenance window on S100P.",
    "Create operator_approval/qwen_systemd_apply_approved.json with approved=true, operator, timestamp, target_unit_sha256, maintenance_window, rollback_acknowledged=true.",
    "Required target_unit_sha256: d4f3a198305894becde33cc318c24b23ac14a1664dc62d5c89a6102c90b783a0",
    "Rerun Stage2.10."
  ]
}
```
