# 21220 journal_live_regression_gate

- generated_at: 2026-07-04T08:32:15Z
- status: skipped
- verdict: blocked_by_no_operator_approval

```json
{
  "approval": {
    "approval_file": "operator_approval/digua_journal_live_rollout_approved.json",
    "approval_file_exists": false,
    "approval_file_payload": null,
    "approved": false,
    "env_name": "AI_NAS_OPERATOR_APPROVED_DIGUA_JOURNAL_LIVE_ROLLOUT",
    "env_value_is_1": false
  },
  "disable_script_verified_for_existence": true,
  "generated_at": "2026-07-04T08:32:15Z",
  "hard_constraints": {
    "cloud_generation_enabled": false,
    "delete_move_rename_chmod_executed": false,
    "desktop_visual_enabled": false,
    "keyboard_mouse_tracking_enabled": false,
    "openclaw_replaced": false,
    "ports_8765_18080_18888_18889_modified": false,
    "private_nas_raw_content_uploaded": false,
    "qwen_replaced": false,
    "qwen_tool_execution_authority": false,
    "screenshot_enabled": false
  },
  "live_rollout_attempted": false,
  "openclaw_reload_attempted": false,
  "reason": "missing operator approval gate",
  "regression_not_run_reason": "live rollout did not start because operator approval was absent",
  "report_id": 21220,
  "s100p_service_mutation_attempted": false,
  "ssh_attempted": false,
  "status": "skipped",
  "title": "journal_live_regression_gate",
  "verdict": "blocked_by_no_operator_approval"
}
```
