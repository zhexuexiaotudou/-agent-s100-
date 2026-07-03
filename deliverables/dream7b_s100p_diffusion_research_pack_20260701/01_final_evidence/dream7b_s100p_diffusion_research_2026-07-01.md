# Dream7B S100P Diffusion Research Result

Date: 2026-07-01

## Decision

The seq128 Dream7B diffusion HBM path is now proven to compile and run on S100P,
but it is blocked at the logits numerical gate and must not be promoted to
foreground OpenClaw traffic.

Layered result:

| Gate | Result | Evidence |
| --- | --- | --- |
| `compile_feasible` | pass | local seq128 tar SHA256 matched `c0e7d6c31af17871cf550ceec88c1bf1ec8de33f30f4d75a9f7b31aa1b73e1b1`; manifest rows `28` |
| `s100p_runtime_valid` | pass | S100P loaded and ran representative segments `0:1`, `5:6`, `27:28`, then the full 28-segment chain |
| `logits_numerically_valid` | fail | GGUF reference vs BPU last-token logits failed on both `zeros` and `ramp` 128-token cases |
| `generation_quality_valid` | not run | blocked by logits failure |
| `product_route_valid` | not run | blocked by logits failure |

Final research packet:

```text
tmp/product_guardrail_snapshots/dream7b_s100p_diffusion_research_packet_20260701-015545/dream7b_s100p_diffusion_research_packet.json
tmp/product_guardrail_snapshots/dream7b_s100p_diffusion_research_packet_20260701-015545/dream7b_s100p_diffusion_research_packet.md
/mnt/nas/openclaw/reports/models/dream7b_s100p_diffusion_research_packet_20260701-015545/dream7b_s100p_diffusion_research_packet.json
/mnt/nas/openclaw/reports/models/dream7b_s100p_diffusion_research_packet_20260701-015545/dream7b_s100p_diffusion_research_packet.md
```

Final verdict:

```text
falsified_or_blocked_dream7b_seq128_logits_numerical_gate
falsification_layer: logits_numerically_valid
```

## What Was Executed

New reusable probes:

```text
scripts/probes/dream7b_s100p_diffusion_research_packet.py
scripts/probes/dream7b_seq128_s100p_runtime_gate.py
scripts/probes/dream7b_seq128_logits_reference_compare.py
```

The verified seq128 package was staged on NAS under an isolated directory:

```text
/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken
```

It contains `28` HBM files and does not overwrite the existing seq16 baseline.

S100P runtime gate:

```text
/mnt/nas/openclaw/reports/models/dream7b_seq128_s100p_runtime_gate_20260701-014346/seq128_s100p_runtime_gate.json
```

Summary:

```text
verdict: ok_dream7b_seq128_s100p_runtime_gate
representative segments: pass, executed_count=3
full chain: pass, executed_count=28
final_shape: [1, 152064]
representative_total_load_ms: 25191.438
representative_total_run_ms: 80.688
full_chain_total_load_ms: 75503.263
full_chain_total_run_ms: 317.142
errors: []
```

Logits reference comparison:

```text
/mnt/nas/openclaw/reports/models/dream7b_seq128_logits_reference_compare_20260701-015037/seq128_logits_reference_compare.json
```

Summary:

```text
verdict: blocked_dream7b_seq128_logits_reference_compare
reference: gguf_q4km_dump_logits
case_count: 2
top1_agreement: 0.0
ref_top1_in_bpu_top5: 0.0
mean_cosine: 0.0
min_cosine: 0.0
mean_bpu_top1_probability: 0.000006576178451178451
max_bpu_normalized_entropy: 1.0
```

Per-case result:

| Case | GGUF top1 | BPU top1 | Cosine | BPU entropy |
| --- | ---: | ---: | ---: | ---: |
| `zeros` | `151643` | `152063` | `0.0` | `1.0` |
| `ramp` | `151643` | `152063` | `0.0` | `1.0` |

The BPU last-token logits were effectively uniform/zero in both cases. This is
not acceptable for generation or product routing.

## Boundary

This execution did not enable `18889`, did not route foreground OpenClaw traffic
to BPU, did not overwrite `18888`, and did not delete seq16 artifacts.

Post-run checks:

```text
exp18889_proc: none
seq128_proc: none
dump_logits_proc: none
seq128_hbm: 28
seq16_dirs: 10
```

`dream7b-bpu-batch-queue.service` was observed `inactive/enabled` during this
run; it was already inactive at the start of the S100P snapshot and was not
started, stopped, or restarted by these probes.

## Interpretation

This result narrows the answer:

- It is false that Dream7B seq128 is only a cloud compile artifact now. It has
  been staged on NAS and has passed S100P representative and full-chain
  load/run shape validation.
- It is also false that this is deployable as an accurate foreground diffusion
  model today. The first numerical logits gate failed hard against the available
  GGUF q4km reference.

The reference used here is GGUF q4km, not BF16. Therefore this result should be
read as a deployment-blocking numerical mismatch against the current product
reference, not as a final proof that the HBM graph is mathematically wrong
against an ideal BF16 implementation.

## Next Research Step

Do not run generation-quality or 18889 product-route gates until the logits
failure is explained.

The next useful work is a narrow logits-debug task:

1. Inspect whether `seg27_28` returns all-zero int16 logits before dequantization.
2. Compare the BPU final segment with a BF16/PyTorch or compiler-side reference
   on the same hidden input, not only GGUF q4km.
3. Verify whether `lm_head_w_bits=16` plus `last-token` changed the final model
   name/output quantization in a way the runtime postprocessing currently
   mishandles.
4. Only after top-k/cosine/entropy metrics pass should generation quality or
   18889 isolation tests resume.
