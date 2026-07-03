# 010 Triplet Reference Alignment Design

## Hypothesis

The existing GGUF Q4_K_M mismatch blocks deployment, but it does not prove BF16/PyTorch ground-truth failure. A three-way alignment framework is required before the S100P HBM graph can be called mathematically wrong.

## Method

The framework compares one shared set of seq128 token-id cases across three references:

1. BF16/PyTorch reference logits from `tools/export_bf16_reference_logits.py`.
2. GGUF Q4_K_M deployment reference logits from `tools/export_gguf_reference_logits.py`.
3. S100P BPU/HBM dequantized logits from `tools/run_s100p_hbm_chain_dump_logits.py`.

`tools/compare_logits_triplet.py` computes top-1 agreement, top-5 overlap, reference-top1-in-candidate-top5, cosine, relative L2, max/mean absolute error, KL divergence, entropy, normalized entropy, top-1 probability, nonzero count, and NaN/Inf count.

## Alignment Controls

- Tokenizer mismatch is avoided by storing explicit `token_ids` in JSONL cases. Semantic decoding remains a separate evidence item.
- Position mismatch is avoided by storing explicit `position_ids = 0..127`.
- Padding mismatch is recorded through `nonpad_count`, `mask_positions`, and `attention_mask`.
- Last-token slicing mismatch is controlled by recording `expected_last_token_index = 127` for BF16, GGUF, and BPU.

## Current Boundary

BF16/PyTorch export requires a verified Dream7B forward wrapper and checkpoint path. Until that exists, Gate 2 remains unresolved against BF16 and deployment remains blocked only against the available GGUF reference.

