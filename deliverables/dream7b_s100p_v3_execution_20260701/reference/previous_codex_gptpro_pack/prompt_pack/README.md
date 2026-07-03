# Dream7B on S100P 分层证实/证伪研究：Codex Prompt Pack

用途：把当前 Dream7B diffusion 在 S100P 上的研究，从“seq128 HBM 已编译、S100P 可 load/run/shape，但 GGUF-reference logits 门失败”的状态，推进到可审计的最终判定。

最终目标不是“让它看起来能跑”，而是用可复现实验证据回答：

> Dream7B diffusion on S100P 是否在 `seq128, B=1, segmented HBM, lm_head q16, last-token logits` 链路上达到准确部署？

## 使用方法

建议把本包复制到你的项目根目录，例如：

```text
dream7b-s100p-research/
  dream7b_s100p_diffusion_research_pack_20260701/
  codex_dream7b_s100p_research_prompt_pack_20260701/
  scripts/
  tools/
  reports/
  evidence/
```

然后按顺序把 `prompts/` 里的内容喂给 Codex。

优先执行顺序：

1. `00_MASTER_PROMPT.md`
2. `01_REPRODUCE_EXISTING_EVIDENCE.md`
3. `02_TRIPLET_REFERENCE_ALIGNMENT_FRAMEWORK.md`
4. `03_S100P_BPU_DUMP_LOGITS.md`
5. `05_FINAL_SEGMENT_LMHEAD_Q16_AUDIT.md`
6. `07_DEQUANT_AUDIT.md`
7. `09_BUILD_GATE_PACKET.md`

`10_GENERATION_QUALITY_GATE.md` 和 `11_PRODUCT_ROUTE_ISOLATION_GATE.md` 是后置任务，只有 Gate 2 logits 数值门明确通过后才能执行。

## 当前证据边界

当前可支持的有限结论：

- seq128 B=1 segmented HBM artifact：compile feasible。
- S100P tested chain：可 load/run，并输出 `[1,152064]` shape。
- against GGUF Q4_K_M dump-logits reference：tested BPU logits path 失败。
- Generation quality：pending / blocked。
- Product route：pending / blocked。
- 18888 foreground route 不得被切换到 BPU。

## 禁止越界

不得写：

- “Dream7B 已经在 S100P 上准确部署。”
- “所有 diffusion model 都不能在 S100P 上部署。”
- “GGUF Q4_K_M mismatch 等价于 BF16 ground-truth failure。”
- “Gate 3/4 failed”，除非真的执行并失败。
- “seq16 negative control 直接证明 seq128 失败。”

可以写：

- “tested seq128 HBM chain passed compile and S100P board load/run/shape gates.”
- “tested BPU logits path failed numerical validation against available GGUF Q4_K_M deployment reference.”
- “BF16/PyTorch reference is required to distinguish HBM graph defect from reference mismatch.”
