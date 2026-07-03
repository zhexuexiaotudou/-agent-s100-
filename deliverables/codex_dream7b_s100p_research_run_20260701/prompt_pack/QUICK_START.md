# 最小推进路线

如果只想快速推进，不要一次开太多 Codex 任务。按下面 5 步做。

## Step 1：复现证据包

使用：

```text
prompts/01_REPRODUCE_EXISTING_EVIDENCE.md
```

产出：

```text
reports/000_reproduce_existing_evidence.json
reports/000_reproduce_existing_evidence.md
scripts/check_review_pack_integrity.py
```

目标：确认目前证据没有被误读。

## Step 2：建立三路 reference 框架

使用：

```text
prompts/02_TRIPLET_REFERENCE_ALIGNMENT_FRAMEWORK.md
```

产出 BF16 / GGUF / BPU logits 对齐工具。

目标：把“GGUF reference 失败”推进到“BF16 ground truth 是否失败”。

## Step 3：保存完整 BPU logits

使用：

```text
prompts/03_S100P_BPU_DUMP_LOGITS.md
```

目标：不能只看 top-k，必须保存 raw output 与 dequantized full logits。

## Step 4：优先审计 final segment 与 dequant

使用：

```text
prompts/05_FINAL_SEGMENT_LMHEAD_Q16_AUDIT.md
prompts/07_DEQUANT_AUDIT.md
```

目标：判断 entropy=1 / logits 全零到底是 lm_head、last-token slicing、vocab layout，还是 dequant/postprocess bug。

## Step 5：生成 gate packet

使用：

```text
prompts/09_BUILD_GATE_PACKET.md
```

目标：把结果聚合成最终 pass/fail/blocked/inconclusive 判定包。

## 暂时不要做

在 Gate 2 没过之前，不要执行：

```text
prompts/10_GENERATION_QUALITY_GATE.md
prompts/11_PRODUCT_ROUTE_ISOLATION_GATE.md
```

原因：logits 数值门没过时，生成质量和产品路由没有测试意义。
