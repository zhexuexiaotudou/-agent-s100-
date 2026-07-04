# Digua AI-NAS Harness Stage3 Readonly Shadow Gate Packet

- final_verdict: `stage3_readonly_shadow_pass_but_hold_for_longer_soak`
- all_stage3_gates_pass: `True`
- stage4_entered: `False`
- requires_gptpro_or_human_review_before_stage4: `True`

| Report | Gate | Verdict | Checks | Failures |
|---|---|---:|---:|---:|
| `11000_stage3_fasttrack_baseline_lock` | `stage3_fasttrack_baseline_lock` | `ok_stage3_fasttrack_baseline_lock` | 9/9 | 0 |
| `11010_stage3_shadow_tap_integrity_gate` | `stage3_shadow_tap_integrity_gate` | `ok_stage3_shadow_tap_integrity_gate` | 6/6 | 0 |
| `11020_stage3_policy_first_shadow_decision_gate` | `stage3_policy_first_shadow_decision_gate` | `ok_stage3_policy_first_shadow_decision_gate` | 7/7 | 0 |
| `11030_stage3_readonly_shadow_execution_gate` | `stage3_readonly_shadow_execution_gate` | `ok_stage3_readonly_shadow_execution_gate` | 11/11 | 0 |
| `11040_stage3_health_resource_latency_gate` | `stage3_health_resource_latency_gate` | `ok_stage3_health_resource_latency_gate` | 10/10 | 0 |
| `11045_stage3_cloud_egress_redaction_gate` | `stage3_cloud_egress_redaction_gate` | `ok_stage3_cloud_egress_redaction_gate` | 6/6 | 0 |
| `11050_stage3_shadow_rollback_gate` | `stage3_shadow_rollback_gate` | `ok_stage3_shadow_rollback_gate` | 9/9 | 0 |
| `11060_stage3_final_gate_packet` | `stage3_final_gate_packet` | `stage3_readonly_shadow_pass_but_hold_for_longer_soak` | 9/9 | 0 |

## Package

- Latest local zip: `evidence_for_gptpro/digua_ai_nas_harness_stage3_readonly_shadow_for_gptpro_20260704-003851.zip`.
- SHA256: `a3de87e77b61d55e1e9ea0b5765d456a400922af8b63b2131cda8fbfe53c0eb9`.
- File count: `600`.
- Trust the adjacent `.sha256.txt` for package-level verification.
