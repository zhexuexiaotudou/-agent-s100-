# Digua Project Retrospective 2026-06-23

## Executive Conclusion

After review and discussion, Dream7B should not remain the model direction for
this project. The useful outcome of the Dream7B phase is not the deployed model
itself, but the reusable engineering chain built around it:

- S100P bring-up and PC-to-board networking.
- NAS mount and OpenClaw service connectivity checks.
- systemd service templates and deployment guardrails.
- OpenAI-compatible gateway patterns.
- Queue-backed batch execution and telemetry collection.
- Evidence packets in Markdown/JSON.
- Promotion gates, rollback checks, and isolated experiment ports.
- Compile/runtime inventory methods for large BPU artifacts.

The next project phase should carry these tools forward to a better model or a
different local-intelligence workload, instead of continuing to optimize
Dream7B as the product model.

## Work Timeline

### 1. S100P Bring-Up

The project started by making S100P usable from a Windows workstation:

- Board flashing and vendor package collection.
- PC-to-S100P network wiring and SSH access.
- Startup link checks for S100P, NAS, NFS, and OpenClaw/Feishu.
- Reusable operator notes in `docs/s100p_agent_based_bringup.md`.

Primary artifacts:

- `docs/s100p_agent_based_bringup.md`
- `docs/startup_link_check_2026-06-09.md`
- `scripts/startup_link_check/`
- `logs/link-check/`

### 2. AI-NAS / OpenClaw Product Layer

The workspace then grew into an AI-NAS proof path: NAS files, local tools,
approval/rollback controls, search/OCR/photo/document probes, and OpenClaw
entry routing.

This part remains valuable even without Dream7B.

Primary reusable assets:

- `scripts/probes/ai_nas_*.py`
- `scripts/probes/ai_nas_*.sh`
- `configs/systemd/openclaw-gateway.service`
- `configs/systemd/ai-nas-index-daemon.service`
- `docs/ai_nas_mvp/`

### 3. Dream7B Route A: User-Facing GGUF / Gateway Path

Dream7B was first kept behind an OpenAI-compatible gateway. By 2026-06-22, the
safe product-facing path was:

```text
OpenClaw -> dream7b-local-openai-gateway:18888 -> diffuse-resident -> Dream7B GGUF
```

This path was stabilized for deterministic identity/status/ready prompts and
bounded AI-NAS demo flows. It did not prove Dream7B was a strong general chat
model. Generic generation still took seconds and could return short or wrong
answers.

Primary artifacts:

- `docs/dream7b_openclaw_fast_path_fix_2026-06-22.md`
- `scripts/diffuse_resident.cpp`
- `scripts/probes/dream7b_fast_path_regression_probe.py`
- `scripts/probes/dream7b_first_response_slo_tier_guard.py`
- `scripts/probes/dream7b_route_a_quality_boundary_packet.py`

### 4. Dream7B Route B: BPU Queue / True-Batch Research Path

The BPU path produced the densest reusable engineering work:

- Queue-batch baseline.
- True-batch compile and HBM artifact inventory.
- Segment-major runtime probes.
- Load attribution, scheduler overhead analysis, and final-logits analysis.
- Same-workload comparisons across batch sizes.
- Isolated 18889 experiment gateway design.
- Promotion and rollback gate packets.

Important runtime conclusion:

- Queue-batch remained the production baseline during the Dream7B phase.
- True-batch artifacts were runtime-valid, but shape correctness and throughput
  experiments did not clear product-quality gates.
- B=16 was the best same-workload true-batch runtime candidate in the prior
  selection work, but that was a runtime result, not a product suitability
  result.
- The BPU single-request path stayed structurally blocked for foreground chat
  because of seq16 prompt truncation and logits/generation quality gaps.
- A later 512 GiB x86_64 cloud compile window produced a complete
  `seq128, B=1` segmented HBM package on 2026-06-23. This reduced the compile
  feasibility question but did not validate S100P runtime, logits quality,
  Chinese generation, or product suitability. The closure artifact is
  `docs/dream7b_seq128_cloud_compile_closure_2026-06-23.md`.

Primary artifacts:

- `docs/dream7b_deployment_baseline.md`
- `docs/dream7b_deployment_file_map.md`
- `docs/dream7b_true_batch_b4_segment_analysis_2026-06-19.md`
- `docs/dream7b_seq128_cloud_compile_closure_2026-06-23.md`
- `docs/dream7b_openclaw_two_track_deployment_2026-06-22.md`
- `scripts/probes/dream7b_true_batch_*.py`
- `scripts/probes/dream7b_b4_*.py`
- `scripts/probes/dream7b_bpu_quality_*.py`
- `scripts/telemetry/`

## Final Dream7B Assessment

Dream7B is not suitable as the project model because the product-facing path
and BPU path each have a hard boundary:

- Route A can support a controlled demo, but generic generation remains slow
  and unreliable enough that it should be described as a boundary, not a solved
  model experience.
- Route B has useful throughput and telemetry machinery, but it is blocked by
  board-side runtime validation, logits quality, Chinese generation quality,
  and missing promotion evidence. The 2026-06-23 `seq128` cloud package answers
  only compile feasibility; it does not change the product decision.
- More Dream7B tuning would likely add engineering debt faster than it adds
  project value.

The reusable result is the surrounding system: bring-up, service isolation,
queueing, probes, telemetry, gates, rollback, and report packaging.

## What To Keep

Keep as reusable project assets:

- S100P bring-up and link-check workflow.
- AI-NAS probes and report packet style.
- systemd service templates as deployment examples.
- OpenAI-compatible gateway patterns.
- Queue-backed async/batch job contract.
- Telemetry parsers and same-workload comparison discipline.
- Promotion gates that separate demo readiness from production readiness.
- Rollback/dry-run scripts and service freshness gates.

Keep as historical evidence, not active direction:

- Dream7B docs under `docs/dream7b_*.md`.
- Dream7B true-batch and BPU quality probes.
- `tmp/product_guardrail_snapshots/`.
- `tmp/remote_true_batch_reports/`.
- NAS-backed Dream7B report paths referenced from the docs.
- The verified local `seq128` HBM package under
  `tmp/cloud_seq128_results/`, until it is deliberately copied to NAS or
  deleted after a separate retention decision.

Treat as high-risk large artifacts:

- `tmp/autodl_*_results/`
- `tmp/seg*_calib*/`
- `tmp/true_batch_inputs/`
- `tmp/wsl/`
- `product/`
- `downloads/`

Do not delete these without a separate inventory and retention decision.

## Recommended Next Phase

1. Pick the next model/workload first; do not start by porting Dream7B-specific
   runtime assumptions.
2. Reuse the S100P/NAS/OpenClaw scaffolding.
3. Fork only generic probes first: health, latency, queue, telemetry, report
   packets, rollback, and promotion gates.
4. Keep model-specific names, ports, and service aliases isolated until the new
   candidate has passed a demo-readiness gate.
5. Convert any new model experiment into the same evidence format:
   Markdown summary, JSON report, explicit verdict, inputs, outputs, and
   rollback boundary.
