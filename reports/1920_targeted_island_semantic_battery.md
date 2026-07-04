# Targeted Island Semantic Battery

- semantic_cases_generated: `8`
- hf_truth_rows: `0`
- island_rows: `0`
- verdict: `semantic_battery_runtime_blocked_no_logits_rows`

## Blocking or Failure Reasons
- HF/PyTorch BF16 truth for semantic cases could not be produced because the installed transformers 4.30.2 path still attempted torch.load on sharded safetensors.
