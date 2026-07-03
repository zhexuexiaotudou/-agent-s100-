# 07 DEQUANT AUDIT

请审计 S100P BPU/HBM output dequantization 链路。

## 目标

确认 raw output tensor 到 float logits 的转换公式正确。

## 任务

1. 阅读 runtime API 或现有脚本中 dequant 相关代码。
2. 新建：

```text
tools/audit_output_dequant.py
```

3. 对 BPU final output 保存并比较：

```text
raw dtype
raw min/max/mean/std
scale
zero_point
dequant formula
dequant min/max/mean/std
nonzero_count before/after dequant
```

4. 尝试所有合理 dequant variants，但不要把猜测写成事实：

```text
y = scale * x
y = scale * (x - zero_point)
per-tensor scale
per-channel scale
signed vs unsigned interpretation
int16 endian / layout reinterpretation
```

5. 每个 variant 输出：

```text
top-k
entropy
cosine vs BF16/GGUF reference
```

## 输出

```text
reports/060_dequant_audit.json
reports/060_dequant_audit.md
```

## 判定

- 如果某个 dequant variant 显著恢复 cosine/top-k，标注为 likely postprocess/dequant bug。
- 如果 raw output 本身全零或常数，标注为 upstream graph/runtime/lm_head issue。
- 如果 raw output 有信息但 official dequant 输出全零，优先修 dequant path。
