# Task 140 — BF16/PyTorch reference wrapper

## Goal

Establish a BF16/PyTorch reference only if the exact checkpoint, tokenizer, code path, model semantics, position ids, and seq128 last-token indexing are available.

## Required tools

Create or update:

```text
tools/export_bf16_reference_logits.py
tools/export_bf16_boundaries.py
```

You may start from the scaffolds, but do not guess unsupported Dream7B diffusion semantics.

## Requirements

- Same token ids as BPU/GGUF cases.
- Same position ids.
- Same seq_len = 128.
- Same last_token_index = 127 unless a report proves otherwise.
- Save BF16/PyTorch last-token logits `.npy`.
- Save BF16/PyTorch boundary activations only if segment-to-layer mapping is verified.
- Include:
  - checkpoint path
  - checkpoint SHA256 or file manifest SHA256
  - tokenizer identity/hash
  - model code revision
  - dtype
  - device
  - wrapper limitations

## Failure mode

If BF16 cannot be established, output:

```json
{
  "bf16_reference_status": "unavailable",
  "reason": "...",
  "no_bf16_ground_truth_claims_allowed": true
}
```

Do not claim BF16 failure without BF16 evidence.

## Outputs

- `reports/140_bf16_reference_status.json`
- `reports/140_bf16_reference_status.md`
- optional `evidence/bf16_reference_v3/{run_id}/...`
