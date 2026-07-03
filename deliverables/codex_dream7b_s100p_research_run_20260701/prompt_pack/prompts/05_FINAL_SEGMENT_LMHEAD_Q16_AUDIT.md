# 05 FINAL SEGMENT LM_HEAD Q16 AUDIT

请对 Dream7B seq128 HBM final segment `seg27_28` / `lm_head q16` 做隔离实验。

## 目标

判断 final logits uniform/zero 是来自：

```text
A. seg27_28 graph 本身错误
B. lm_head q16 quantization/export 错误
C. last-token slicing 错误
D. output dequant scale/postprocess 错误
E. vocab layout 或 logits buffer interpretation 错误
```

## 任务

### 1. 检查 final segment metadata

找到 seq128 manifest 中 `seg27_28` 的：

```text
HBM/HBO file
input tensor name
output tensor name
shape
dtype
quantization metadata
```

新建：

```text
tools/inspect_final_segment_metadata.py
```

输出：

```text
segment file path
file size
sha256
input tensors
output tensors
declared output shape
quantization params
lm_head weight bits
vocab size
```

### 2. final segment isolated run

新建：

```text
tools/run_final_segment_isolated.py
```

输入：

```text
BF16/reference hidden state
或 previous segment output
```

只运行 final segment，并保存：

```text
raw logits
dequant logits
metadata
```

### 3. 测试三类 input

```text
real seg26 output from BPU
BF16 seg26 hidden state transformed into expected BPU input layout
synthetic nonzero hidden vectors with controlled values
```

## 输出

```text
reports/040_final_segment_lmheadq16_audit.json
reports/040_final_segment_lmheadq16_audit.md
```

## 必须回答

- final segment 是否对 nonzero input 产生 nonzero logits？
- output scale 是否为 0、NaN、极小值或异常常数？
- top-k 是否随 input 改变？
- logits buffer 是否可能被错误地当成全零/常数？
- 是否存在 off-by-one last-token index 或只取到了 padding/mask token hidden state？
