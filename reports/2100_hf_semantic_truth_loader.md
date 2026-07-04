# HF Semantic Truth Loader

- semantic_cases_generated: `8`
- semantic_truth_rows: `0`
- verdict: `blocked_by_reference_runtime`

## Blocking or Failure Reasons
- semantic HF/PyTorch BF16/FP32 full-truth logits were not produced; semantic island and generation gates remain locked

## Next Blocking Condition
- Need a compatible HF runtime (torch>=1.9 with safetensors/transformers support, or vendor-provided semantic truth rows) before semantic island validation.
