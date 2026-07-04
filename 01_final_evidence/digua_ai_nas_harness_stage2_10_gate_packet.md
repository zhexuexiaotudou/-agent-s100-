# Digua AI-NAS Harness Stage 2.10 Gate Packet

- final_verdict: `ready_for_stage3_readonly_shadow_dryrun_policy_first`
- stage3_allowed: `True`
- all_stage2_10_gates_pass: `True`

| Report | Gate | Verdict | Checks | Failures |
|---|---|---:|---:|---:|
| `9000_stage2_10_baseline_lock` | `stage2_10_baseline_lock` | `ok_stage2_10_baseline_lock` | 8/8 | 0 |
| `9010_operator_approval_hard_gate` | `stage2_10_operator_approval_hard_gate` | `ok_stage2_10_operator_approval_hard_gate` | 3/3 | 0 |
| `9020_qwen_persistence_apply_verify_restart_gate` | `stage2_10_qwen_persistence_apply_verify_restart_gate` | `ok_stage2_10_qwen_persistence_apply_verify_restart_gate` | 9/9 | 0 |
| `9030_qwen_persistence_rollback_verify_gate` | `stage2_10_qwen_persistence_rollback_verify_gate` | `rollback_plan_verified_dry_run` | 6/6 | 0 |
| `9040_post_persistence_policy_first_readonly_shadow_soak_gate` | `stage2_10_post_persistence_readonly_shadow_soak_gate` | `ok_stage2_10_post_persistence_readonly_shadow_soak_gate` | 10/10 | 0 |
| `9050_stage2_10_stage3_go_no_go_gate` | `stage2_10_stage3_go_no_go_gate` | `ready_for_stage3_readonly_shadow_dryrun_policy_first` | 11/11 | 0 |
