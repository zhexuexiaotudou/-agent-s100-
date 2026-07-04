# Stage 3 Readonly Shadow Dry-Run Plan V5

Stage 3 name: `Stage 3 Readonly Shadow Dry-Run, Policy-First Mode`.

Entry requirements:

1. Operator approval passes.
2. Qwen service is applied.
3. `qwen25-local-openai-gateway.service` is active and enabled.
4. Qwen restart test passes.
5. Rollback plan is verified.
6. Post-persistence readonly shadow soak passes.
7. No write/destructive/admin/recovery workspace is exposed.
8. No production route change occurs.
9. No private cloud egress occurs.
10. OpenClaw and Qwen health pass.

Stage 2.10 entry evidence:

- `operator_approval/qwen_systemd_apply_approved.json`
- `reports/9000_stage2_10_baseline_lock.json`
- `reports/9010_operator_approval_hard_gate.json`
- `reports/9020_qwen_persistence_apply_verify_restart_gate.json`
- `reports/9030_qwen_persistence_rollback_verify_gate.json`
- `reports/9040_post_persistence_policy_first_readonly_shadow_soak_gate.json`
- `reports/9050_stage2_10_stage3_go_no_go_gate.json`
- `reports/stage2_10_post_persistence_shadow_soak_trace.jsonl`
- `01_final_evidence/digua_ai_nas_harness_stage2_10_gate_packet.json`

Stage 2.10 observed state:

- Qwen persistence status: `applied_and_verified`.
- Qwen role: structured decision disabled, advisor disabled safe mode, execution authority false.
- Soak trace completeness: `1.0`.
- Final tool source policy rate: `1.0`.
- Protected ports unchanged: `True`.

Allowed scope:

- OpenClaw foreground path unchanged
- local Qwen gateway unchanged except persistence management
- sidecar/harness shadow observation only
- `nas_search` readonly
- `document_rag` readonly
- deterministic policy chooses workspace/tool
- dispatcher executes only allowlisted read-only tools
- runtime trace, redaction, and rollback evidence

Forbidden:

- write/destructive/admin/recovery operations
- sidecar as foreground gateway
- Qwen autonomous tool router
- private cloud egress
- Dream7B foreground
- PostgreSQL/pgvector as default dependency
