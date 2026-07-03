# Next Codex Prompt After GPT Pro Review

你是 Dream7B S100P 部署验证工程代理。GPT Pro 已复核 `codex_dream7b_s100p_research_gptpro_pack_20260701.zip`，当前状态仍是：

- verdict: `deployment_blocked_against_deployment_reference_but_bf16_unresolved`
- compile_feasible: pass
- s100p_runtime_valid: pass
- logits_numerically_valid: inconclusive against BF16, fail/blocking against GGUF Q4_K_M deployment reference
- generation_quality_valid: pending/blocked
- product_route_valid: pending/blocked

不要运行 generation quality。不要启用产品路由。不要改动 18888。

## 关键新观察

`seg27_28 / lm_head q16` 隔离实验显示：

1. synthetic hidden inputs `zeros/ones/ramp/last_token_impulse` 能产生非全零 logits，且 top1 随输入变化。
2. 真实 segmented chain 的 `real_bpu_seg26_output` 输入到 `seg27_28` 时，final raw/dequant logits 全零。
3. full-chain 10 个 probe cases final raw output 全零/常数，normalized entropy = 1.0。
4. BF16/PyTorch reference 仍缺失，所以不能写 BF16 falsified。

因此下一步不是继续扩大 prompt，也不是产品路由，而是定位 `seg26_27 -> seg27_28` input contract / layout / dtype / scale / runtime handling。

## Task 1: package hygiene

修复打包：zip 内路径必须使用 POSIX `/`，不要使用 Windows `\`。下一版包必须包含：

- `GPT_PRO_REVIEW_AFTER_CODEX_20260701.md`
- reports JSON/MD
- scripts/tools
- raw evidence subset：
  - one BPU full-chain raw/dequant final logits `.npy`
  - one GGUF last-logits `.npy`
  - BPU `seg26` raw/dequant output `.npy`
  - isolated `seg27_28` synthetic hidden input/output `.npy`
  - isolated `seg27_28` real_bpu_seg26_output input/output `.npy`
- `RAW_EVIDENCE_SUBSET_MANIFEST.json` with size and SHA256 for every included binary.

## Task 2: inspect segment input/output contract

新增 `tools/inspect_segment_io_contract.py`。

For each segment 0..27, output JSON containing every accessible runtime metadata field:

- model names
- input tensor names
- output tensor names
- declared input shapes
- declared output shapes
- input dtype if available
- output dtype if available
- input quant params if available
- output quant params
- hbm path, hbm size, hbm sha256
- model-specific metadata strings

不要只读 `output_quants`；必须尝试读取 `input_quants`、input descriptors、tensor descriptors、model info 等 runtime 暴露字段。无法读取的字段要记录 `unavailable` 和 exception type。

输出：

- `reports/110_segment_io_contract.json`
- `reports/110_segment_io_contract.md`

## Task 3: final segment input sweep

新增 `tools/run_final_segment_input_sweep.py`。

Inputs:

- real `seg26` dequant output from BPU
- real `seg26` raw int16 output, if runtime accepts or can be tested safely
- scaled real dequant output: `x`, `x/2`, `x/4`, `x/8`, `x/16`, `x/32`, `x/64`
- clipped real dequant output: clip to `[-16,16]`, `[-8,8]`, `[-4,4]`, `[-2,2]`, `[-1,1]`
- z-normalized real dequant output
- synthetic tensor matching real seg26 mean/std
- synthetic tensor matching real seg26 min/max distribution
- prior synthetic controls: zeros, ones, ramp, last_token_impulse

For each input variant, run only `seg27_28` and save:

- input stats
- raw output `.npy`
- dequant logits `.npy`
- output stats
- entropy / normalized entropy
- top-20 logits
- nonzero count
- NaN/Inf count
- whether logits are all-zero/constant

Output:

- `reports/120_final_segment_input_sweep.json`
- `reports/120_final_segment_input_sweep.md`

Required analysis:

- Identify the smallest scaling/clipping variant that changes output from all-zero to nonconstant.
- If scaled/clipped real hidden works, suspect range/input-quant contract or saturation.
- If raw int16 works but dequant float fails, suspect runtime input dtype/quantization contract.
- If no real-derived variant works but synthetic does, suspect layout or distribution-specific runtime/kernel defect.

## Task 4: robust boundary dump without HBRT memory failure

Current boundary dump completed zeros but failed ramp at final segment load with HBRT memory allocation error. Rewrite boundary dumping to run each case in a fresh subprocess, and optionally each segment in a fresh process if necessary.

新增/更新:

- `tools/run_s100p_hbm_chain_dump_boundaries_subprocess.py`

Output:

- `reports/130_s100p_boundary_dump_subprocess.json`
- `reports/130_s100p_boundary_dump_subprocess.md`

Requirements:

- At least `zeros`, `ramp`, and one semantic prompt case.
- Save seg24/25/26/27 raw/dequant tensors for each included case.
- Record memory errors as evidence, but do not let one case abort all remaining cases.

## Task 5: BF16/PyTorch reference wrapper

Implement only if the checkpoint and dependencies are available. Do not guess unsupported model semantics.

新增/完成:

- `tools/export_bf16_reference_logits.py`
- `tools/export_bf16_boundaries.py`

Requirements:

- Same token ids, position ids, seq_len=128, last_token_index=127.
- Save BF16 last logits `.npy` and boundary activations if mapping is verified.
- Include checkpoint path, checkpoint SHA256 or file manifest SHA256, tokenizer identity, dtype, device, code revision, and wrapper limitations.

If BF16 cannot be established, keep `bf16_reference_status = unavailable` and do not claim BF16 failure.

## Task 6: build gate packet v3

Update `tools/build_dream7b_s100p_gate_packet.py` so it no longer hard-codes BF16 status. It must support:

- A: accurate deployment supported
- B: deployment falsified against BF16 reference
- C: deployment blocked against deployment reference but BF16 unresolved
- D: inconclusive due to missing artifact/reference/input alignment

Generate:

- `01_final_evidence/dream7b_s100p_gate_packet_v3.json`
- `01_final_evidence/dream7b_s100p_gate_packet_v3.md`
- `01_final_evidence/dream7b_s100p_final_technical_report_v3.md`

Do not mark Gate 3 or Gate 4 pass/fail unless Gate 2 passes and those gates actually run.

## Safe current claim boundary

Use this wording unless new BF16 evidence changes it:

> Dream7B seq128 B=1 segmented HBM with lm_head q16 last-token logits passed compile feasibility and S100P load/run/shape checks. However, the tested BPU logits path is blocked against the available GGUF Q4_K_M deployment reference, and BF16/PyTorch ground truth is unresolved. Current evidence localizes the anomaly to the real segmented chain output path around `seg26_27 -> seg27_28` or final-segment input/runtime interpretation, because isolated `seg27_28` responds to synthetic hidden inputs but outputs all-zero logits for real BPU `seg26` hidden states.
