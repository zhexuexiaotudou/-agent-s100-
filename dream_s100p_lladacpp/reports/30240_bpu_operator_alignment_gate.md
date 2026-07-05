# BPU Operator Alignment Gate

- Verdict: `bpu_operator_alignment_failed_review_required`
- Required ops covered: `False`
- Position path pass: `False`
- Embedding pass: `False`
- lm_head pass: `False`

Reason: no true per-op BPU output checksum table exists for the llada.cpp-style track. Continuing to layer, quant, graph compile, or runtime would overclaim evidence.
