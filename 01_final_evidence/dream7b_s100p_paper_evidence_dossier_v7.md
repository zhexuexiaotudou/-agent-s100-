# Dream7B/S100P v7 Paper Evidence Dossier

## Conclusion

v7 does not validate accurate Dream7B deployment and does not falsify the model against BF16/PyTorch full-model truth. It moves the thread beyond v6 by packaging all-segment S100P boundary evidence and by comparing BPU `seg27_28` against HF final RMSNorm plus `lm_head` on the same BPU hidden input.

## Boundary Localization

`reports/500_all_segment_boundary_raw_audit.json` records raw and dequant arrays for `seg00..27` on zeros, ramp, and short-Chinese cases. The corrected first-extreme table supersedes the v6 wording: earlier int16 extremes occur before `seg20`, so v7 must not claim first saturation at `seg20`.

## Final Segment Function

`reports/510_hf_final_norm_lmhead_only_route.json` exports HF final-head-only logits from BPU final-segment input tensors. `reports/520_final_segment_functional_compare.json` compares those logits against BPU `seg27_28` logits for the same hidden inputs. If the BPU row is all-zero while HF final head is nonzero, the evidence supports a final-segment contract/runtime fault rather than a generation-quality issue.

## Reference Boundary

`reports/530_reference_matrix_completion.json` still lacks a full BF16/FP32 or GGUF F16 truth row. Q4_K_M remains a deployment-reference blocker, not mathematical truth. Therefore the v7 verdict is `E_final_segment_contract_fault_strongly_supported_but_full_reference_unresolved`.

## Claim Boundary

Allowed: all-segment raw boundary packaging, earlier-than-seg20 saturation correction, same-input HF final-head vs BPU final-segment mismatch, and full-reference blocker status. Forbidden: accurate S100P deployment, BF16 falsification, validated scale fix, generation quality claims, or product-route claims.
