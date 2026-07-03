# Digua AI-NAS Harness Stage 2.8 Gate Packet

- final_verdict: `blocked_by_no_operator_approval_for_qwen_persistence`
- stage3_allowed: `False`
- all_stage2_8_gates_pass: `False`

| Report | Gate | Verdict | Checks | Failures |
|---|---|---:|---:|---:|
| `7000_stage2_8_baseline_lock` | `stage2_8_baseline_lock` | `ok_stage2_8_baseline_lock` | 8/8 | 0 |
| `7010_qwen_systemd_apply_verify_rollback_gate` | `stage2_8_qwen_systemd_apply_verify_rollback_gate` | `blocked_by_no_operator_approval` | 12/13 | 1 |
| `7020_policy_first_shadow_contract_gate` | `stage2_8_policy_first_shadow_contract_gate` | `ok_stage2_8_policy_first_shadow_contract_gate` | 11/11 | 0 |
| `7030_qwen_advisor_schema_gate` | `stage2_8_qwen_advisor_schema_gate` | `failed_stage2_8_qwen_advisor_schema_gate` | 9/11 | 2 |
| `7040_policy_first_readonly_shadow_preflight_soak_gate` | `stage2_8_readonly_shadow_preflight_soak_gate` | `ok_stage2_8_readonly_shadow_preflight_soak_gate` | 15/15 | 0 |
| `7050_stage2_8_stage3_go_no_go_gate` | `stage2_8_stage3_go_no_go_gate` | `blocked_by_no_operator_approval_for_qwen_persistence` | 7/8 | 1 |
