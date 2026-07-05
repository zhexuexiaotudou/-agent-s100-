# Dream7B S100P llada.cpp-Style Decision

Updated: 2026-07-04T11:14:10.683800+00:00

The next Dream7B route is not another full-BPU segmented-HBM compile and not an
OpenClaw product integration. The route is a correctness-first, llada.cpp-style
block runtime track:

1. Freeze the v21 negative/partial evidence.
2. Export a complete PyTorch reference truth set.
3. Implement a PyTorch block-wise diffusion driver.
4. Validate BPU operators and layers before static block graphs.
5. Add quantization, KV/revision/logits optimizations, and memory staging only
   after numeric truth gates pass.
6. Validate fixed block tasks before any broader generation claim.

Current decision: `external_truth_missing_hold`.

The available v21 semantic truth removes the old v20 blocker for 8 original
semantic prompts, but it does not satisfy the full 31-row truth contract for
this track. BPU runtime claims stay locked.

Product boundary: Qwen + OpenClaw remains the current AI-NAS product route.
Dream7B must stay out of OpenClaw foreground traffic until a future candidate
passes logits, block, fixed-task, and quality gates.
