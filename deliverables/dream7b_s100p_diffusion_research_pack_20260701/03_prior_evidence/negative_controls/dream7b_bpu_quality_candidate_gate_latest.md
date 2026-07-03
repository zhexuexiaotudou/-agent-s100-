# Dream7B BPU Quality Candidate Gate

- generated_at: `2026-06-22T18:00:21.528050+08:00`
- verdict: `ok_dream7b_bpu_quality_candidate_gate`
- compile_started: `False`
- service_restarted: `False`
- production_write_performed: `False`

## Decision

- Route A remains the product path: OpenClaw -> 18888 -> diffuse-resident -> Dream7B GGUF.
- Route B remains isolated BPU R&D. It may prepare candidate bundles, but this gate does not admit compile, service replacement, or 18888 changes.
- Current BPU seq16 artifacts stay as the queue-batch throughput and telemetry baseline.

## Guardrail

- dream7b_bpu_batch_queue: active=`True`
- dream7b_local_openai_gateway: active=`True`
- openclaw_gateway: active=`True`
- gateway_18888: ok=`True` status=`200`
- openclaw_18789: ok=`True` status=`200`
- compile_process_active: `False`

## Candidate Order

1. `bpu_logits_quality_candidate`: q16 or calibrated `lm_head` plus late segments `seg21_24`, `seg24_26`, `seg26_28`.
2. `bpu_larger_window_candidate`: isolated `fine-seq128` or `fine-seq256` artifacts after capacity planning.

## Acceptance Before Promotion

- logits argmax agreement above 80 percent.
- top-1 probability above 5 percent, not near-uniform logits.
- readable Chinese output on at least three prompts.
- same-workload latency and rollback report.
- Route A services and NAS evidence remain unchanged.

## Errors

- none

## Warnings

- none
