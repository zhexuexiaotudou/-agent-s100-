# stage2_9_operator_approval_check

- verdict: `blocked_by_no_operator_approval`
- generated_at: `2026-07-03T23:44:09.175143+08:00`
- passed: `2/3`

## Checks

- `PASS` candidate unit hash available
- `FAIL` operator approval present and valid
- `PASS` no apply performed by approval check

## Failures

- `operator approval present and valid`

## Detail

```json
{
  "approval": {
    "operator_approved": false,
    "env_approved": false,
    "approval_file": "F:\\Project\\Digua\\operator_approval\\qwen_systemd_apply_approved.json",
    "approval_file_exists": false,
    "approval_file_valid": false,
    "approval_file_error": "missing",
    "approval_file_payload": null,
    "target_unit_sha256": "d4f3a198305894becde33cc318c24b23ac14a1664dc62d5c89a6102c90b783a0"
  },
  "next_manual_steps_if_blocked": [
    "Review deployment/qwen25-local-openai-gateway.service.candidate.",
    "Confirm maintenance window on S100P.",
    "Create operator_approval/qwen_systemd_apply_approved.json with approved=true, operator, timestamp, target_unit_sha256, maintenance_window, rollback_acknowledged=true.",
    "Rerun Stage2.9 gates."
  ]
}
```
