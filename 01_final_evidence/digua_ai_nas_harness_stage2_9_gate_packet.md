# Digua AI-NAS Harness Stage 2.9 Gate Packet

- final_verdict: `blocked_by_no_operator_approval_for_qwen_persistence`
- stage3_allowed: `False`
- all_stage2_9_gates_pass: `False`

| Report | Gate | Verdict | Checks | Failures |
|---|---|---:|---:|---:|
| `8000_stage2_9_baseline_lock` | `stage2_9_baseline_lock` | `ok_stage2_9_baseline_lock` | 8/8 | 0 |
| `8010_operator_approval_check` | `stage2_9_operator_approval_check` | `blocked_by_no_operator_approval` | 2/3 | 1 |
| `8020_qwen_persistence_apply_verify_restart_gate` | `stage2_9_qwen_persistence_apply_verify_restart_gate` | `skipped_no_operator_approval` | 1/2 | 1 |
| `8030_qwen_persistence_rollback_gate` | `stage2_9_qwen_persistence_rollback_gate` | `rollback_plan_verified_dry_run` | 6/6 | 0 |
| `8040_post_persistence_policy_first_readonly_shadow_soak_gate` | `stage2_9_post_persistence_readonly_shadow_soak_gate` | `skipped_qwen_persistence_not_applied` | 0/1 | 1 |
| `8050_stage2_9_stage3_go_no_go_gate` | `stage2_9_stage3_go_no_go_gate` | `blocked_by_no_operator_approval_for_qwen_persistence` | 6/12 | 6 |
