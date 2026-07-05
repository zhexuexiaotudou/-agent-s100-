# Phase 0 Baseline Lock

Verdict: `phase0_baseline_locked`

Current full-BPU path: `falsified_against_HF_PyTorch_BF16_logits_truth`

Semantic truth: v21 has 8/8 original semantic HF/PyTorch BF16 truth rows; full llada-style 31-row truth_cases.jsonl is not yet exported

Seg00_01 status: strongest localized contract-fault locus from prior v14-v21 route; exact closure remains vendor/compiler metadata blocked

Generation quality: `not_run_by_design`

Product route: `not_run_by_design; Qwen + OpenClaw remains current product route`

## Blockers

- Current full-BPU segmented-HBM path is logits-invalid.
- No semantic BPU island passed all original semantic prompts under strict logits gates.
- The llada-style block driver cannot be truth-gated until the full 31-row reference truth set exists.
- No product or generation route may be touched before logits and fixed-task gates pass.

## Claim Boundary

Allowed: Dream7B is in research/evidence mode; v21 provides semantic HF truth
but no deployable BPU route.

Forbidden: do not claim OpenClaw foreground deployment, general dialogue
deployment, BPU success from CPU/GGUF residency, or deployability from partial
semantic island passes.
