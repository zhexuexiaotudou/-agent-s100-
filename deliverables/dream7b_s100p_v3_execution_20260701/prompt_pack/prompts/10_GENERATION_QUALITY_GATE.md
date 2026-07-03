# 10 GENERATION QUALITY GATE

只有 Gate 2 `logits_numerically_valid` 明确通过后，才允许执行本任务。

如果 Gate 2 没有明确 pass，立即停止。

## 任务

设计并运行 seq128 Dream7B S100P generation quality gate，但仍不得启用 foreground product route。

新建：

```text
cases/generation_quality_prompts.jsonl
```

包含：

```text
Chinese prompts
English prompts
short QA
long context
OpenClaw-style prompts
edge cases
```

对每个 prompt 同时运行：

```text
BF16/PyTorch reference generation
GGUF deployment reference generation
S100P BPU/HBM experimental generation
```

固定 sampling 参数：

```text
temperature
top_p
max_new_tokens
seed
diffusion-specific decoding params
```

计算：

```text
empty reply rate
garbled text rate
token leak rate
repetition loop rate
semantic acceptability manual-review slots
output length distribution
latency
```

## 输出

```text
reports/080_generation_quality_gate.json
reports/080_generation_quality_gate.md
```

## 限制

- 如果 logits gate 没有明确 pass，立即停止。
- 如果 generation quality fail，不要改 product route。
- 不得把主服务 18888 指到 BPU。
