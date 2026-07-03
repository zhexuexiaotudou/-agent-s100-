# 08 EXPANDED LOGITS PROBE BATTERY

请扩展 Dream7B seq128 logits probe battery，用于判断当前失败是否只发生在 zeros/ramp，还是普遍发生在真实 prompt。

## 任务

新建：

```text
cases/seq128_logits_probe_battery.jsonl
```

至少包含：

```text
zeros
ramp
repeated frequent token
repeated rare token
alternating two tokens
short English prompt padded to 128
short Chinese prompt padded to 128
OpenClaw-style prompt padded to 128
exactly 128-token synthetic prompt
prompt with mask tail
```

为每个 case 保存：

```text
human description
token_ids
decoded text if applicable
expected last_token_index
whether it is semantic or diagnostic
```

使用 triplet compare framework 比较：

```text
BF16
GGUF
BPU
```

## 输出

```text
reports/070_logits_probe_battery_triplet.json
reports/070_logits_probe_battery_triplet.md
```

## 限制

不要运行 generation quality。

不要连接 product route。

结论只允许写：

```text
logits gate pass
logits gate fail
logits gate inconclusive
blocked by input/reference/artifact issue
```
