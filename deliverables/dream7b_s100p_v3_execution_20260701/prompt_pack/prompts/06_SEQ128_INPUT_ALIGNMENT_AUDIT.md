# 06 SEQ128 INPUT ALIGNMENT AUDIT

请做 Dream7B seq128 输入语义审计，重点检查 token ids、padding、mask、position ids 和 last-token logits index 是否在 BF16、GGUF、BPU 三路完全一致。

## 任务

新建：

```text
tools/audit_seq128_inputs.py
```

对每个 probe case 输出：

```text
token_ids length
first 16 tokens
last 16 tokens
nonpad_count
mask positions
position_ids
last_token_index used by BF16
last_token_index used by GGUF dump
last_token_index used by BPU/HBM output
```

对 real prompt padded case，输出 decoded prompt head/tail，确认没有被截断为 seq16 tail。

检查 zeros/ramp case 是否是合法模型输入；如果它们只是 diagnostic tensors，明确标注。

## 输出

```text
reports/050_seq128_input_alignment_audit.json
reports/050_seq128_input_alignment_audit.md
```

## 硬判定

必须给出：

```text
input_alignment_valid: pass/fail/inconclusive
```

如果 fail，停止解释 logits mismatch 为模型错误，先修 input alignment。
