# Dream7B/S100P Paper Tables v11

## Table 1. Repeat Truth

| Case | Top1 agreement vs v10 | Relative L2 | Pearson | Artifact |
|---|---:|---:|---:|---|
| zeros | True | 0 | 1 | `evidence/full_truth_repeat_v11/zeros/repeat_full_truth_logits.npy` |
| ramp | True | 0 | 1 | `evidence/full_truth_repeat_v11/ramp/repeat_full_truth_logits.npy` |
| short_chinese_prompt_padded | True | 0 | 1 | `evidence/full_truth_repeat_v11/short_chinese_prompt_padded/repeat_full_truth_logits.npy` |

## Table 2. First Divergence

| Case | First divergent segment | Criterion |
|---|---:|---|
| zeros | 0 | relL2>0.1 or Pearson<0.95 |
| ramp | 0 | relL2>0.1 or Pearson<0.95 |
| short_chinese_prompt_padded | 0 | relL2>0.1 or Pearson<0.95 |

## Table 3. Suffix Route Summary

| Boundary | Rows | Top1 agreement | Median relL2 | Median Pearson |
|---:|---:|---:|---:|---:|
| 8 | 3 | 0 | 0.36483010734570137 | 0.7738799236962725 |
| 11 | 3 | 0 | 0.5439676217073303 | 0.7268482008437188 |
| 12 | 3 | 0 | 0.7695447913051602 | 0.39622286170800675 |
| 13 | 3 | 0 | 1.0143631234079535 | 0.34768120741850733 |
| 20 | 3 | 0 | 0.6944710626344935 | 0.6430598489163829 |
| 26 | 3 | 0 | 1.383325206753448 | -0.24282643221749534 |

## Table 4. Blockers

| Area | Status |
|---|---|
| GGUF F16 | Only Q4_K_M GGUF was found in prior and v10 NAS inventory; no GGUF F16/unquantized runner artifact is available in the current workspace/NAS evidence. |
| Operator graph | operator_graph_unavailable |
| Repair | v11 did not find a rebuilt/calibrated artifact. v10 offline affine calibration lowered L2 but kept top1 agreement at 0/42, so no repair is supported. |
