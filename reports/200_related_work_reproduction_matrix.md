# llada.cpp / llama.cpp-npu Inspired Replication Matrix

Scope: this track borrows system design and validation methods only. It does not port Qualcomm Hexagon code to S100P, does not run generation quality, does not enable product routing, and does not touch port 18888.

## Materials Read

| Material | What is reused | S100P replication boundary |
| --- | --- | --- |
| [Efficient On-Device Diffusion LLM Inference with Mobile NPU](https://arxiv.org/html/2606.13740v1) | Use an NPU-aware split between dense accelerator work and CPU-side correction/logits work.; Use selective CPU logits work as a diagnostic pattern for vocabulary-sized lm_head pressure.; Use graph-guided tensor residency, staging, and producer-consumer lifetimes as validation concepts. | Do not port Qualcomm Hexagon code.; Run S100P segments 0..26, dump seg26 hidden, and try CPU/HF lm_head as a hybrid localization test.; Interpret the result only as logits numerical validity and root-cause localization. |
| [Scaling LLM Test-Time Compute with Mobile NPU on Smartphones](https://arxiv.org/html/2509.23324v1) | Treat mobile NPU execution as hardware-layout-sensitive, not as a generic CPU/GPU backend.; Audit quantized dequantization, signedness, byte order, and tile or stride layout before blaming model quality.; Separate offline layout or quantization choices from runtime dequant and vector access behavior. | Add per-tensor/per-channel scale availability checks.; Compare official dequant, signed/unsigned reinterpretation, endian swap, and layout variants.; Record raw int min/max/std and nonzero_count for final logits and late hidden states. |
| [llama.cpp examples/diffusion README](https://github.com/ggml-org/llama.cpp/blob/master/examples/diffusion/README.md) | Diffusion CLI uses explicit diffusion steps, token-selection algorithms, block length, context, batch, and ubatch controls.; Dream and LLaDA GGUF examples are supported as diffusion text-generation architectures. | Keep probe cases as explicit token IDs, position IDs, attention masks, and last-token index.; Do not run generation quality in this track; use logits-only probes. |
| [diffuse-cpp Dream/LLaDA GGUF conversion and quantization README](https://github.com/iafiscal1212/diffuse-cpp) | Dream-v0-Instruct-7B conversion to GGUF F16 is documented via convert-dream.py.; Q4_K_M, Q8_0, and F16 are documented quantization/reference formats.; The runtime operates on token IDs, which matches the seq128 probe-case strategy. | Use GGUF F16/Q4_0/Q4_K_M as reference-matrix rows when artifacts exist.; Current local evidence has Q4_K_M only; F16 and Q4_0 remain missing artifacts. |

## Replication Track

| Upstream method | S100P diagnostic adaptation | Output |
| --- | --- | --- |
| llada.cpp CPU-side logits path | Run BPU segments 0..26, dump seg26 hidden, then compute final lm_head on CPU/HF when a verified Dream BF16 wrapper exists | `reports/220_hybrid_bpu_hidden_cpu_lmhead.json` |
| llada.cpp graph-guided runtime validation | Treat seg26 hidden and seg27_28 final logits as a producer-consumer contract instead of a single black-box output | `reports/230_final_segment_input_contract_sweep.json` |
| llama.cpp-npu quant/layout audit | Check official dequant, scalar/channel scale availability, signedness, byte order, and layout implications before making quality claims | `reports/240_s100p_dequant_layout_audit.json` |
| llama.cpp/diffuse-cpp GGUF references | Compare the same seq128 token-id cases across BF16, GGUF F16, GGUF Q4_0, GGUF Q4_K_M, and S100P raw/dequant when artifacts exist | `reports/210_reference_matrix_logits_compare.json` |

## Current Artifact Boundary

- Available: GGUF Q4_K_M logits, S100P BPU raw/dequant final logits, S100P seg24..27 boundary dumps, final segment input sweep.
- Unavailable in the current v3 evidence set: verified Dream BF16/PyTorch forward wrapper, HF seg26 boundary hidden, GGUF F16 logits, GGUF Q4_0 logits, CPU/HF lm_head logits.
- Therefore, conclusions remain at logits numerical validity and root-cause localization. They are not generation-quality or product-route claims.
