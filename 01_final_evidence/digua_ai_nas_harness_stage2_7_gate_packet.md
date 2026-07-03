# Digua AI-NAS Harness Stage 2.7 Gate Packet

- final_verdict: `ready_with_fixes_before_stage3`
- all_stage2_7_gates_pass: `False`

| Report | Gate | Verdict | Checks | Failures |
|---|---|---:|---:|---:|
| `6000_stage2_7_baseline_lock` | `stage2_7_baseline_lock` | `ok_stage2_7_baseline_lock` | 6/6 | 0 |
| `6005_package_self_rerun_repair_gate` | `stage2_7_package_self_rerun_repair_gate` | `ok_stage2_7_package_self_rerun_repair_gate` | 7/7 | 0 |
| `6010_qwen_service_persistence_closure_gate` | `stage2_7_qwen_service_persistence_closure_gate` | `ok_stage2_7_qwen_service_persistence_closure_gate_candidate_not_applied` | 7/7 | 0 |
| `6020_qwen_structured_decision_contract_gate` | `stage2_7_qwen_structured_decision_contract_gate` | `failed_stage2_7_qwen_structured_decision_contract_gate` | 8/12 | 4 |
| `6030_qwen_driven_readonly_agent_loop_gate` | `stage2_7_qwen_driven_readonly_agent_loop_gate` | `failed_stage2_7_qwen_driven_readonly_agent_loop_gate` | 0/1 | 1 |
| `6040_qwen_driven_agent_loop_soak_gate` | `stage2_7_qwen_driven_agent_loop_soak_gate` | `failed_stage2_7_qwen_driven_agent_loop_soak_gate` | 0/1 | 1 |
| `6050_qwen_driven_vs_policy_first_architecture_decision` | `stage2_7_architecture_decision_gate` | `ok_stage2_7_architecture_decision_gate` | 5/5 | 0 |
| `6060_stage3_readonly_shadow_go_no_go_gate` | `stage2_7_stage3_readonly_shadow_go_no_go_gate` | `failed_stage2_7_stage3_readonly_shadow_go_no_go_gate` | 11/12 | 1 |
