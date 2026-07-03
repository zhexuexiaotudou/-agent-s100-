# Task 120 — Final segment input sweep

## Hypothesis

`seg27_28 / lm_head q16` is not globally dead, because synthetic hidden inputs produce non-zero logits. Real BPU `seg26` hidden states may violate the expected final-segment input contract or trigger saturation/runtime handling that produces all-zero logits.

## Required tool

Create or update:

```text
tools/run_final_segment_input_sweep.py
```

You may start from `tools_scaffold/run_final_segment_input_sweep.py`, but must replace the runtime adapter with the actual S100P/HBRT invocation.

## Input variants

Use the same real `seg26` output that produced all-zero final logits in v2. For each case save input `.npy`, raw output `.npy`, dequant output `.npy`, and metadata.

Required variants:

- real `seg26` dequant output: `x`
- scaled real dequant output: `x/2`, `x/4`, `x/8`, `x/16`, `x/32`, `x/64`
- clipped real dequant output: clip to `[-16,16]`, `[-8,8]`, `[-4,4]`, `[-2,2]`, `[-1,1]`
- z-normalized real dequant output
- synthetic tensor matching real `seg26` mean/std
- synthetic tensor matching real `seg26` min/max distribution
- synthetic controls: zeros, ones, ramp, last_token_impulse
- real `seg26` raw int16 output if final segment runtime can safely accept/test raw input

## Required metrics per variant

Input stats:

- shape
- dtype
- min/max/mean/std
- nonzero count
- NaN/Inf count
- absolute max
- percentile summary: p0, p1, p5, p50, p95, p99, p100

Output stats:

- raw dtype/min/max/mean/std/nonzero/constant/allzero
- dequant dtype/min/max/mean/std/nonzero/constant/allzero
- top-20 logits
- entropy
- normalized entropy
- top1 probability
- NaN/Inf count

## Required analysis

Answer:

1. What is the smallest scaling/clipping variant that changes final output from all-zero/constant to nonconstant?
2. If scaled/clipped real hidden works, does this indicate range/input-quant contract or saturation?
3. If raw int16 works but dequant float fails, does this indicate dtype/quant contract mismatch?
4. If no real-derived variant works but synthetic controls work, does this indicate layout/distribution-specific runtime/kernel defect?
5. Does top-k change monotonically or sensibly across input variants?

## Outputs

- `reports/120_final_segment_input_sweep.json`
- `reports/120_final_segment_input_sweep.md`
- `evidence/final_segment_input_sweep/{run_id}/{variant}/input.npy`
- `evidence/final_segment_input_sweep/{run_id}/{variant}/raw_output.npy`
- `evidence/final_segment_input_sweep/{run_id}/{variant}/dequant_logits.npy`
- `evidence/final_segment_input_sweep/{run_id}/{variant}/metadata.json`

## Verdict

```json
{
  "final_segment_input_sweep_verdict": "pass|fail|inconclusive|blocked",
  "real_hidden_constant_output": true,
  "synthetic_controls_nonconstant": true,
  "smallest_recovery_variant": null,
  "likely_issue_class": "input_range_or_scale|dtype_or_quant_contract|layout_or_distribution_specific|final_segment_runtime_kernel|inconclusive"
}
```
