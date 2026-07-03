# Task 930 GGUF F16 Reference Crosscheck

- schema: `dream7b_s100p_v11_930_gguf_f16_reference_crosscheck`
- created_at_utc: `2026-07-01T19:15:57.094670+00:00`
- gguf_f16_available: `False`
- primary_truth: `HF/PyTorch BF16`
- blocking_or_failure_reasons:
  - Only Q4_K_M GGUF was found in prior and v10 NAS inventory; no GGUF F16/unquantized runner artifact is available in the current workspace/NAS evidence.
- next_minimal_experiments:
  - Provide Dream7B GGUF F16/unquantized artifact and llama.cpp/diffuse-cpp runner for canonical seq128 logits cross-check.
