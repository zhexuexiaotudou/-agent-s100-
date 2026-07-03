# Reusable Toolchain Map 2026-06-23

This map separates reusable engineering assets from Dream7B-specific history.

## Reusable Asset Groups

### S100P Bring-Up And Link Checks

Purpose: make a fresh S100P reachable and verify its dependency chain.

Keep:

- `docs/s100p_agent_based_bringup.md`
- `docs/startup_link_check_2026-06-09.md`
- `scripts/startup_link_check/`
- `logs/link-check/`

Reusable pattern:

- Verify PC-to-board network first.
- Verify SSH key access.
- Verify NAS/NFS mount and write permission.
- Verify OpenClaw entry health.
- Keep JSONL logs for later evidence.

### Service Templates And Routing Policies

Purpose: deploy services with explicit ports, environment variables, and
rollback boundaries.

Keep:

- `configs/systemd/openclaw-gateway.service`
- `configs/systemd/ai-nas-index-daemon.service`
- `configs/systemd/dream7b-local-openai-gateway.service`
- `configs/systemd/dream7b-bpu-batch-queue.service`
- `configs/systemd/dream7b-bpu-experimental-gateway-18889.service`
- `configs/dream7b_queue_adapter_policy.json`
- `configs/dream7b_backend_policy.yaml`

Reuse note:

The Dream7B names should not be copied blindly into the next model. Reuse the
structure: protected product port, isolated experiment port, explicit fallback,
and a policy file that rejects foreground traffic until gates pass.

### AI-NAS Probes

Purpose: validate product behavior independent of Dream7B.

Script family:

- `scripts/probes/ai_nas_*.py`
- `scripts/probes/ai_nas_*.sh`
- shared helper: `scripts/probes/ai_nas_common.py`

Reusable coverage:

- file search and folder summaries
- OCR and document pipeline
- photo similarity and semantic search
- duplicate report
- edge/cloud router
- approval inbox and destructive-action governance
- evidence freshness and catalog contracts
- production readiness gates
- operator portal contracts
- queue/backpressure and tail-latency checks

### Gateway And First-Response Validation

Purpose: prevent demos from regressing into slow or wrong first responses.

Keep:

- `scripts/probes/dream7b_fast_path_regression_probe.py`
- `scripts/probes/dream7b_first_response_packet.py`
- `scripts/probes/dream7b_first_response_fast_status_packet.py`
- `scripts/probes/dream7b_first_response_routing_packet.py`
- `scripts/probes/dream7b_first_response_slo_tier_guard.py`
- `scripts/probes/dream7b_openclaw_default_latency_probe.py`

Reuse note:

Rename these for the next model, but keep the idea: deterministic status
prompts should have a separate fast path and a measurable SLO. Generic model
generation should not be allowed to masquerade as demo readiness.

### Queue And Telemetry

Purpose: compare backends by normalized evidence rather than single anecdotes.

Keep:

- `scripts/telemetry/run_queue_baseline_telemetry.ps1`
- `scripts/telemetry/run_true_batch_telemetry.ps1`
- `scripts/telemetry/parse_bpu_telemetry.py`
- `scripts/telemetry/compare_backends.py`
- `scripts/probes/dream7b_queue_health_snapshot.py`
- `scripts/probes/dream7b_queue_partial_batch_flush_probe.py`

Reusable pattern:

- Same workload across candidates.
- Explicit processed request count and failed job count.
- Full-window utilization and active/nonzero utilization reported separately.
- Latency, throughput, and failure metrics all required for promotion.

### True-Batch / BPU Runtime Research

Purpose: preserve the tooling techniques without preserving Dream7B as a goal.

Keep as reference:

- `scripts/probes/dream7b_true_batch_*.py`
- `scripts/probes/dream7b_true_batch_*.sh`
- `scripts/probes/dream7b_b4_*.py`
- `scripts/probes/analyze_dream_true_batch_b4.py`
- `scripts/probes/Compile-DreamTrueBatchSegments.ps1`
- `scripts/probes/compile_dream_true_batch_segments.sh`

Reusable techniques:

- segment inventory and manifest checks
- HBM load accounting
- group-major telemetry
- runtime chain verification
- schedule analysis
- final-logits attribution
- capacity and admission gates

Dream7B-specific conclusions should not be transferred to another model unless
the new model repeats equivalent same-workload tests.

### Quality, Promotion, And Rollback Gates

Purpose: separate experiment success from product promotion.

Keep:

- `scripts/probes/dream7b_bpu_quality_*.py`
- `scripts/probes/dream7b_product_decision_packet.py`
- `scripts/probes/dream7b_product_guardrail_snapshot.py`
- `scripts/probes/dream7b_default_service_freshness_gate.py`
- `scripts/probes/dream7b_gateway_listener_ownership_probe.py`
- `scripts/probes/dream7b_gateway_listener_drift_gate.py`
- `scripts/probes/dream7b_two_track_deployment_audit.py`
- `scripts/probes/dream7b_workstream_overlap_audit.py`

Reusable rule:

Every future candidate should produce one promotion packet with explicit
`pass`, `blocked`, or `fail` reasons. A shape-correct artifact, a fast isolated
microbenchmark, or a demo-only fast path is not enough for promotion.

## Repo Hygiene Notes

- `tmp/` is the dominant local size source and contains both valuable evidence
  and disposable scratch. Do not clean it without a separate inventory.
- `scripts/**/__pycache__/` and Python bytecode are disposable cache.
- `tmp/phase1-builder/venv/` is an environment snapshot, not source.
- `product/` and `downloads/` contain vendor or binary artifacts; keep until a
  storage retention pass decides otherwise.
- The `.git` directory is empty in this workspace, so Git status is not a
  reliable verification method here.

## Minimal Verification Set

When modifying reusable scripts, run at least:

```powershell
python -m py_compile scripts\probes\ai_nas_common.py
python -m py_compile scripts\telemetry\parse_bpu_telemetry.py scripts\telemetry\compare_backends.py
python -m py_compile scripts\dream7b_experimental_18889_gateway.py
```

When changing a specific probe family, compile the touched files and run the
probe in mock/report-root mode if it supports that mode.

