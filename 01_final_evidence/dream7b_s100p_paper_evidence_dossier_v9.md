# Dream7B/S100P Paper Evidence Dossier v9

## Research Question
Can Dream7B seq128 segmented HBM on S100P produce numerically valid logits?

## Evidence Table

| Evidence row | Status | Claim supported | Main artifact |
|---|---:|---|---|
| Final endpoint raw tensors | 42/42 | Endpoint sweep is replayable | evidence/final_segment_endpoint_raw_v9 |
| Exact HF final boundary | 42/42 | Defines layer27 + final norm + lm_head on same hidden input | evidence/hf_exact_final_segment_v9 |
| Full truth row | blocked | Required for full deployment logits validity | evidence/full_reference_v9 |
| Same-input final comparison | 42/42 | Tests seg27_28 official-dequant against exact HF final segment | evidence/v9_comparisons/exact_final_segment |

## Main Conclusion
For the unmodified BPU seg26 hidden input (real_x) in all three prompt cases, S100P seg27_28 official-dequant logits are all-zero, while the exact HF layer27 + final norm + lm_head boundary produces nonzero/nonconstant logits for the same inputs. Across the 42-row sweep, top-1 agreement is 0/42, 15/42 rows are all-zero/constant against nonconstant HF references, and 36/42 rows have relative L2 > 0.9. This falsifies the final-segment contract on same input. Full deployment logits validity remains unproven without a full truth row.

## Paper-Safe Claims
- For the unmodified real_x endpoint inputs in all three prompt cases, the S100P seg27_28 official-dequant output does not implement the HF layer27 + final norm + lm_head boundary.
- Across the 42-row final-segment sweep, top-1 agreement is 0/42; 15/42 rows are all-zero/constant against nonconstant HF references in this run.
- The same BPU seg26 endpoint hidden produces nonzero/nonconstant logits through the exact HF final boundary.
- Full Dream7B seq128 segmented HBM logits validity on S100P is not established because the full truth row is unavailable.

## Claims Not Supported
- Do not claim generation quality or product-route behavior.
- Do not claim full Dream7B deployment logits are numerically valid.
- Do not claim full Dream7B deployment logits are falsified against BF16/FP32 truth without the missing truth row.
- Do not claim 18888/18889 routes were enabled, tested, or modified.
