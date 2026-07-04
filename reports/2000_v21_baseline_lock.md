# v21 Baseline Lock

- current full-BPU path: falsified against HF/PyTorch BF16 logits truth in prior gates.
- v20 semantic blocker: HF truth rows were missing; v21 resolved this with local CUDA torch2 export.
- generation_quality: not_run_by_design.
- product_route: not_run_by_design; 18888/18889 untouched.
- v21 objective: root evidence closure for semantic islands and position path, not generation quality.
