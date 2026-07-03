# Root Cause Summary v13

seg00_01 has a verified runtime I/O contract and HBIR-level dump, but no full compiler/HBO graph. Decomposition comparison finds no BPU output/input/interpretation variant matching any HF layer0 boundary across all canonical cases, supporting a seg00_01 graph/input/quant contract failure rather than a final lm_head-only issue.
