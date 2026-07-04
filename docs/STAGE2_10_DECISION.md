# Stage 2.10 Decision

Final verdict: `ready_for_stage3_readonly_shadow_dryrun_policy_first`.

Stage 2.10 is limited to operator-approved Qwen systemd persistence closure. Without a valid operator approval file or approval environment variable, no systemd apply is allowed and Stage 3 remains blocked.

Current boundary:

- Qwen structured decision remains disabled.
- Qwen advisor remains disabled safe mode.
- Tool execution authority remains deterministic policy plus `workspace_tool_policy`, `workspace_arg_policy`, and `ai_nas_allowlisted_tool.sh`.
- Stage 3 can only be `Stage 3 Readonly Shadow Dry-Run, Policy-First Mode`.

Successful path recorded:

- Operator approval file: `operator_approval/qwen_systemd_apply_approved.json`.
- Operator: `zhexu`.
- Maintenance window: `2026-07-04T00:07:25+08:00 immediate operator-approved Stage2.10 maintenance window`.
- Target unit SHA256: `d4f3a198305894becde33cc318c24b23ac14a1664dc62d5c89a6102c90b783a0`.
- Systemd unit: `qwen25-local-openai-gateway.service`.
- Apply/restart verification: applied=`True`, active_enabled=`True`, restart_ok=`True`.
- Rollback verification: `rollback_plan_verified_dry_run`.
- Post-persistence soak: run_count=`200`, concurrency=`4`, allowed_success_rate=`1.0`, denial_correctness=`1.0`.
- Safety counters: dispatcher_bypass_count=`0`, private_leak_count=`0`, cloud_private_egress_count=`0`, qwen_execution_authority_count=`0`.
- Health and route boundary: OpenClaw health before/after OK=`True/True`, Qwen health before/after OK=`True/True`, protected_ports_unchanged=`True`.

Gate summary:

| Report | Gate | Verdict | Checks | Failures |
|---|---|---:|---:|---:|
| `9000_stage2_10_baseline_lock` | `stage2_10_baseline_lock` | `ok_stage2_10_baseline_lock` | 8/8 | 0 |
| `9010_operator_approval_hard_gate` | `stage2_10_operator_approval_hard_gate` | `ok_stage2_10_operator_approval_hard_gate` | 3/3 | 0 |
| `9020_qwen_persistence_apply_verify_restart_gate` | `stage2_10_qwen_persistence_apply_verify_restart_gate` | `ok_stage2_10_qwen_persistence_apply_verify_restart_gate` | 9/9 | 0 |
| `9030_qwen_persistence_rollback_verify_gate` | `stage2_10_qwen_persistence_rollback_verify_gate` | `rollback_plan_verified_dry_run` | 6/6 | 0 |
| `9040_post_persistence_policy_first_readonly_shadow_soak_gate` | `stage2_10_post_persistence_readonly_shadow_soak_gate` | `ok_stage2_10_post_persistence_readonly_shadow_soak_gate` | 10/10 | 0 |
| `9050_stage2_10_stage3_go_no_go_gate` | `stage2_10_stage3_go_no_go_gate` | `ready_for_stage3_readonly_shadow_dryrun_policy_first` | 11/11 | 0 |

GPT Pro evidence package:

- Latest local zip: `evidence_for_gptpro/digua_ai_nas_harness_stage2_10_for_gptpro_20260704-001631.zip`.
- SHA256: `eb8d3af92b30bd3197693aec8f2093968bb0295a5241c0be67ac19a41a85705f`.
- File count: `583`.
- A zip cannot contain its own final SHA without changing that SHA; trust the adjacent `.sha256.txt` for package-level verification.
