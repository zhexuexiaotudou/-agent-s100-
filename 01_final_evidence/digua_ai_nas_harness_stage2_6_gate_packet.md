# Digua AI-NAS Harness Stage 2.6 Gate Packet

- final_verdict: `ready_with_fixes_before_stage3`
- all_stage2_6_gates_pass: `False`

| Report | Gate | Verdict | Checks | Failures |
|---|---|---:|---:|---:|
| `5000_stage2_6_baseline_lock` | `stage2_6_baseline_lock` | `ok_stage2_6_baseline_lock` | 6/6 | 0 |
| `5010_qwen_unit_persistence_gate` | `stage2_6_qwen_unit_persistence_gate` | `failed_stage2_6_qwen_unit_persistence_gate` | 4/7 | 3 |
| `5020_agent_loop_qwen_semantic_success_gate` | `stage2_6_agent_loop_qwen_semantic_success_gate` | `failed_stage2_6_agent_loop_qwen_semantic_success_gate` | 10/12 | 2 |
| `5030_agent_loop_soak_gate` | `stage2_6_agent_loop_soak_gate` | `failed_stage2_6_agent_loop_soak_gate` | 8/9 | 1 |
| `5040_sidecar_resource_under_research_load_gate` | `stage2_6_sidecar_resource_under_research_load_gate` | `ok_stage2_6_sidecar_resource_under_research_load_gate` | 7/7 | 0 |
| `5050_stage3_shadow_dryrun_go_no_go_gate` | `stage2_6_stage3_shadow_dryrun_go_no_go_gate` | `failed_stage2_6_stage3_shadow_dryrun_go_no_go_gate` | 8/11 | 3 |
