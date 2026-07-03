# GatherND Embedding Quant Audit

- verdict: `gathernd_matches_hf_embedding_only_after_unacceptable_affine_fit`
- rows: `21`

## Blocking or Failure Reasons
- No known GatherND quant scale/metadata maps the dumped int8 GatherND output to HF token embeddings across all cases.
