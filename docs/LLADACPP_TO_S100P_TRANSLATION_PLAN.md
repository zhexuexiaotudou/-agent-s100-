# llada.cpp To S100P Translation Plan

Primary source: [Efficient On-Device Diffusion LLM Inference with Mobile NPU](https://arxiv.org/html/2606.13740v1)

This is a correctness-first translation plan. It extracts design constraints
from llada.cpp and maps them to S100P, but does not copy any phone-NPU code into
this repo.

| ID | llada.cpp design point | S100P equivalent | Status |
| --- | --- | --- | --- |
| `block_wise_static_window` | Use block-wise denoising windows instead of treating every step as arbitrary-length decoding. | Define fixed block sizes 16, 32, and 64 with static input/output tensor contracts before any full-model graph attempt. | `planned` |
| `multi_block_speculative_decoding` | Admit future-block draft tokens when current-block masked-token count becomes too small. | Represent draft tokens in the scheduler but forbid them from updating committed prefix state until accepted by strict rules. | `planned_after_phase3` |
| `dual_path_progressive_revision` | Keep early visible tokens revisable and refresh unstable tokens through a sparse side path. | Track visible, stable, and revisable masks in CPU-side state; let BPU focus on dense block denoising until a verified sparse path exists. | `planned_after_truth` |
| `prefix_kv_cache_reuse` | Reuse prefix KV state across denoising steps and invalidate only the affected sparse regions. | Start with CPU reference cache hashes and version ids; only promote to BPU visible buffers after layer-level truth passes. | `planned_after_phase5` |
| `selective_logits_skipping` | Skip redundant logits for tokens already stable, especially when lm_head pressure dominates. | Compute logits only for active or uncertain positions after a full-logits comparison proves identical decisions. | `planned_after_phase3` |
| `swap_optimized_memory_runtime` | Use graph-guided NPU-visible memory mapping and pipelined staging. | Define S100P BPU buffer classes for weights, KV/revision state, token state, logits/confidence, and double-buffered staging. | `planned_after_phase7` |
| `operator_library_before_full_graph` | Treat accelerator support as a library of validated ops, not a single opaque full graph. | Build per-op and per-layer gates for embedding, position/RoPE, RMSNorm, QKV, attention, MLP, residual, and lm_head. | `next_after_phase2` |
| `low_bit_quant_with_activation_calibration` | Treat quantization as a runtime and quality loop, not only offline weight compression. | Start with W8A16, record activation ranges by layer, then try W4 only after W8 passes logits gates. | `blocked_until_op_layer_truth` |
| `fixed_task_validation_before_chat` | Validate on fixed output lengths and block tasks before claiming broad generation. | Use eight fixed tasks: command, JSON plan, NAS intent, summary, infill, rewrite, Chinese normalization, and safety refusal. | `phase11_only` |

## Directly Actionable Now

- Create the isolated track directory and safety boundaries.
- Freeze the v21 baseline into Phase 0 reports.
- Define truth-case schema and operator manifest requirements.
- Keep generation, product routing, 18888/18889, and OpenClaw foreground untouched.

## Requires New Implementation

- PyTorch block-wise diffusion driver with token state trace.
- BPU per-op and layer alignment harness.
- Static block graph compiler path for S100P.
- BPU visible memory staging runtime.

## Hold Conditions

- If full 31-row PyTorch truth is missing, hold at external_truth_missing_hold.
- If position, embedding, or lm_head op alignment fails, stop block runtime.
- If only fixed tasks pass, do not claim general dialogue deployment.
