# Task 430 GGUF F16/Q4 Reference Matrix

- verdict: `partial_q4km_only_bf16_or_f16_missing`
- Q4_K_M and HF safetensors are available; comparable BF16/FP32 logits, GGUF F16, and GGUF Q4_0 rows are unavailable.
- Corrected-scale endpoint logits are packaged but cannot be scored for correctness without BF16/GGUF F16.
