# Gate Packet v7

- verdict_class: `E_final_segment_contract_fault_strongly_supported_but_full_reference_unresolved`
- verdict: v7 packages all-segment boundaries and shows that for the same BPU seg26 hidden, HF final RMSNorm+lm_head produces nonzero logits while S100P seg27_28 can return all-zero or mismatched logits. This strongly supports a final-segment contract/runtime fault, but full BF16/GGUF F16 truth remains unavailable.
- Gate 6/7: `not_run_by_design` / `not_run_by_design`
