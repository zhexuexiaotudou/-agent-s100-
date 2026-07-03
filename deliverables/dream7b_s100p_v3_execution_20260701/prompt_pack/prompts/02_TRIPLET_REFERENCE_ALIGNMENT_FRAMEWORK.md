# 02 TRIPLET REFERENCE ALIGNMENT FRAMEWORK

请设计并实现 Dream7B seq128 logits 三路对齐框架。

## 目标

比较同一 checkpoint、同一 tokenizer、同一 token ids、同一 position ids、同一 `seq_len=128`、同一 last-token index 下的三路输出：

```text
1. BF16/PyTorch reference logits
2. GGUF Q4_K_M dump-logits reference logits
3. S100P BPU/HBM dequantized last-token logits
```

## 任务

### 1. 新建 BF16 exporter

新建：

```text
tools/export_bf16_reference_logits.py
```

要求：

- 输入 JSONL cases。
- 每条 case 包含：
  - `case_id`
  - `token_ids`
  - `position_ids`
  - `attention_mask`
  - `expected_seq_len`
- 加载 BF16/PyTorch checkpoint。
- 输出 last-token logits 为 `.npy`。
- 输出 metadata JSON，包含：
  - model path
  - dtype
  - device
  - tokenizer id/hash
  - checkpoint hash
  - seq_len
  - vocab size
  - last_token_index

### 2. 新建 GGUF exporter

新建：

```text
tools/export_gguf_reference_logits.py
```

或封装现有 GGUF dump-logits 路径。

要求输出格式必须与 BF16 exporter 一致。

### 3. 新建三路比较脚本

新建：

```text
tools/compare_logits_triplet.py
```

计算：

```text
top1 agreement
top5 overlap
ref_top1_in_candidate_top5
cosine
L2 relative error
max_abs_error
mean_abs_error
KL divergence after temperature-stabilized softmax
entropy
normalized entropy
top1 probability
nonzero_count
min/max/mean/std
NaN/Inf count
```

### 4. 新建 probe cases

新建：

```text
cases/seq128_probe_cases.jsonl
```

至少包含：

```text
zeros
ramp
single_token_repeat
alternating_tokens
real_prompt_padded
real_prompt_mask_tail
```

### 5. 写设计说明

新建：

```text
reports/010_triplet_reference_design.md
```

说明如何避免：

```text
tokenizer mismatch
position id mismatch
padding mismatch
last-token slicing mismatch
```

## 限制

不要运行需要 S100P 的步骤；先实现 framework 和 dry-run tests。
