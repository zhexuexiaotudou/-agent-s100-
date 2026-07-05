# Phase 2 PyTorch Truth Export Gate

Verdict: `external_truth_missing_hold`

Required truth rows: `31`

Available status:

- v21 original semantic rows: `8`
- v21 total island-eval truth rows: `11`
- block truth rows: `0`
- revision truth rows: `0`
- fixed-output truth rows: `0`
- prompt/infill truth rows: `0`
- control-command truth rows: `0`

Reason: v21 unblocks original semantic HF truth, but this track still lacks the full 31-row PyTorch reference truth set required before any BPU runtime claim.

Next action: Export reference/truth_cases.jsonl on an x86/GPU torch2 environment using semantic, canonical, block-wise, revision, fixed-output, infill, and control-command cases.
