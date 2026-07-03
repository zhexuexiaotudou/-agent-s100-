# 04 SEGMENT BOUNDARY ACTIVATION LOCALIZATION

请实现 segment boundary activation dump，用于定位 Dream7B seq128 HBM chain 从哪个 segment 开始偏离 reference。

## 目标

对同一组 seq128 cases，在每个 segment boundary 保存 hidden state 或可导出的中间 tensor，并与 BF16/PyTorch reference 的对应 layer/block 输出比较。

## 任务

### 1. 新建 S100P boundary dump

新建：

```text
tools/run_s100p_hbm_chain_dump_boundaries.py
```

要求：

- 对 segment `0..27` 执行。
- 每段输出后保存 boundary tensor：

```text
evidence/s100p_boundaries/{run_id}/{case_id}/seg_{i:02d}_output.npy
```

- 同时保存：
  - raw output
  - dequantized output
  - shape
  - scale
  - layout metadata

### 2. 新建 BF16 boundary exporter

新建：

```text
tools/export_bf16_boundaries.py
```

要求：

- 从 PyTorch reference 导出与 HBM segment 对应的 boundary activations。
- 如果 exact layer mapping 不存在，读取 HBM manifest/summary 推断 mapping，并输出 uncertainty。

### 3. 新建 boundary compare

新建：

```text
tools/compare_boundaries.py
```

对每个 segment 计算：

```text
cosine
relative L2
max_abs_error
mean_abs_error
NaN/Inf
min/max/std
```

并生成：

```text
first_divergent_segment
```

## 输出

```text
reports/030_segment_boundary_compare.json
reports/030_segment_boundary_compare.md
```

## 判定规则

- 如果 segment 0 already diverges，优先查 tokenizer/input ids/position ids/input layout。
- 如果 early segments match but later diverge，定位对应 segment graph/quant/layout。
- 如果 seg26 output matches but seg27/lm_head output fails，优先查 lm_head q16、last-token slicing、vocab layout、dequant scale。
- 如果 all hidden boundaries match BF16 but logits fail，问题更可能在 final projection/postprocess/runtime output interpretation。
