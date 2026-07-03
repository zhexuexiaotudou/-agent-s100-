# Codex 执行入口：Dream7B S100P v3 定位任务

你是 Dream7B S100P 部署验证工程代理。先完整阅读本文件，再阅读：

1. `reference/GPT_PRO_REVIEW_AFTER_CODEX_20260701.md`
2. `reference/gptpro_codex_pack_review_summary_20260701.json`
3. `reference/NEXT_CODEX_PROMPT_AFTER_GPTPRO_REVIEW_20260701.md`
4. `reference/previous_codex_gptpro_pack/01_final_evidence/dream7b_s100p_gate_packet_v2.json`
5. `reference/previous_codex_gptpro_pack/reports/*.json` 与 `*.md`

然后在当前 Dream7B/S100P 研究 repo 中执行本轮任务。

## 当前状态

当前 verdict 是：

```text
deployment_blocked_against_deployment_reference_but_bf16_unresolved
```

Gate 状态：

```text
compile_feasible: pass
s100p_runtime_valid: pass
logits_numerically_valid: inconclusive against BF16; fail/blocking against GGUF Q4_K_M deployment reference
generation_quality_valid: pending/blocked
product_route_valid: pending/blocked
```

关键定位：

```text
seg27_28 / lm_head q16 对 synthetic hidden inputs 有响应，但对真实 BPU seg26 output 输入输出全零。full-chain final logits 也全零/常数。
```

这把问题收窄到 `seg26_27 -> seg27_28` 之间的 input contract / layout / dtype / scale / hidden range / runtime interpretation，或 final-segment 对真实 hidden 分布的 kernel/runtime 处理。

## 禁止事项

严格禁止：

1. 不要运行 generation quality gate，除非 v3 Gate 2 明确 pass。
2. 不要启用产品路由。
3. 不要修改或覆盖 18888 foreground route。
4. 不要把 18889 接入真实 foreground traffic。
5. 不要把 GGUF Q4_K_M mismatch 写成 BF16 ground-truth failure，除非 BF16/PyTorch reference 已建立且失败。
6. 不要把 seq16 negative control 当作 seq128 证明。
7. 不要隐藏失败或把 missing artifact 写成 pass。

## 执行顺序

### Step 0 — 包与 repo hygiene

执行 `tasks/000_PACKAGE_AND_REPO_HYGIENE.md`。

交付：

- `reports/105_package_hygiene_v3.json`
- `reports/105_package_hygiene_v3.md`
- 若要给 GPT Pro 回传，最终 zip 路径必须全为 POSIX `/`。

### Step 1 — Segment IO contract audit

执行 `tasks/110_SEGMENT_IO_CONTRACT.md`。

交付：

- `tools/inspect_segment_io_contract.py`
- `reports/110_segment_io_contract.json`
- `reports/110_segment_io_contract.md`

必须尝试读取 input tensor descriptors、input quant params、output quant params、shape、dtype、model names、runtime metadata。读不到就记录 `unavailable` 和 exception type。

### Step 2 — Final segment input sweep

执行 `tasks/120_FINAL_SEGMENT_INPUT_SWEEP.md`。

交付：

- `tools/run_final_segment_input_sweep.py`
- `reports/120_final_segment_input_sweep.json`
- `reports/120_final_segment_input_sweep.md`
- `evidence/final_segment_input_sweep/{run_id}/...`

核心问题：真实 `seg26` hidden 经缩放、裁剪、z-normalize、layout/dtype 变体后，是否能让 `seg27_28` 从全零/常数输出恢复到 nonconstant logits。

### Step 3 — Robust late-boundary dump in subprocesses

执行 `tasks/130_BOUNDARY_DUMP_SUBPROCESS.md`。

交付：

- `tools/run_s100p_hbm_chain_dump_boundaries_subprocess.py`
- `reports/130_s100p_boundary_dump_subprocess.json`
- `reports/130_s100p_boundary_dump_subprocess.md`
- 至少 zeros、ramp、一个 semantic case 的 seg24/25/26/27 raw/dequant tensors。

每个 case 必须 fresh subprocess；必要时每个 segment fresh process。HBRT memory error 是 evidence，不能让一个 case 中止全部任务。

### Step 4 — BF16/PyTorch reference wrapper, only if available

执行 `tasks/140_BF16_REFERENCE_WRAPPER.md`。

交付：

- `tools/export_bf16_reference_logits.py`
- `tools/export_bf16_boundaries.py`
- `reports/140_bf16_reference_status.json`
- `reports/140_bf16_reference_status.md`

如果 checkpoint、tokenizer、model code 或 dependencies 不可用，输出 `bf16_reference_status = unavailable`，不要编造 BF16 结论。

### Step 5 — Gate packet v3

执行 `tasks/150_BUILD_GATE_PACKET_V3.md`。

交付：

- `tools/build_dream7b_s100p_gate_packet_v3.py`
- `01_final_evidence/dream7b_s100p_gate_packet_v3.json`
- `01_final_evidence/dream7b_s100p_gate_packet_v3.md`
- `01_final_evidence/dream7b_s100p_final_technical_report_v3.md`

最终 verdict 必须是以下之一：

```text
A. accurate_deployment_supported
B. deployment_falsified_against_bf16_reference
C. deployment_blocked_against_deployment_reference_but_bf16_unresolved
D. inconclusive_due_to_missing_artifact_reference_or_input_alignment
```

### Step 6 — Evidence zip for GPT Pro

执行 `tasks/160_EVIDENCE_ZIP_FOR_GPTPRO.md`。

交付：

- `dream7b_s100p_research_v3_for_gptpro_YYYYMMDD.zip`
- `RAW_EVIDENCE_SUBSET_MANIFEST.json`
- `MANIFEST.json`
- `SHA256SUMS.txt`

必须包含最小 raw evidence subset：

- one BPU full-chain raw/dequant final logits `.npy`
- one GGUF last-logits `.npy`
- BPU `seg26` raw/dequant output `.npy`
- isolated `seg27_28` synthetic hidden input/output `.npy`
- isolated `seg27_28` real_bpu_seg26_output input/output `.npy`
- final segment input sweep 的代表性 raw/dequant outputs

如果 raw evidence 太大，至少包含 subset，并在 manifest 中列出未包含的 raw evidence 及原因。

## 本轮成功判据

本轮不要求“部署成功”。本轮成功是指能把状态推进为以下之一：

```text
1. 确认 final segment input range/scale/contract 问题，并给出最小恢复变体。
2. 确认 raw int16 vs dequant float 路径差异，定位 dtype/quant contract。
3. 确认真实 hidden 分布或 layout 导致 final segment 输出全零，而 synthetic 控制不触发。
4. 成功建立 BF16 reference，并据此证实或证伪 BPU HBM chain。
5. 若仍不能定位，输出可复核的 inconclusive，并列出唯一下一步实验。
```

## Safe claim boundary

除非本轮 BF16 evidence 改变结论，否则论文/报告只能使用以下边界：

> Dream7B seq128 B=1 segmented HBM with lm_head q16 last-token logits passed compile feasibility and S100P load/run/shape checks. However, the tested BPU logits path is blocked against the available GGUF Q4_K_M deployment reference, and BF16/PyTorch ground truth is unresolved. Current evidence localizes the anomaly to the real segmented chain output path around `seg26_27 -> seg27_28` or final-segment input/runtime interpretation, because isolated `seg27_28` responds to synthetic hidden inputs but outputs all-zero logits for real BPU `seg26` hidden states.
