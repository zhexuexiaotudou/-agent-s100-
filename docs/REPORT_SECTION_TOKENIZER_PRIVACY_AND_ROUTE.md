# Report Section: Tokenizer Privacy And Route

## Privacy Route

Token Budget & Privacy Router 的核心策略是 local-first。所有请求先在本地完成 tokenizer 计数、隐私检查和路由判断；只有被判定为 public 或已脱敏的复杂任务，才允许进入 cloud route。私有 NAS 原文、ACL denied 路径、家庭/财务/证件/secret 等敏感语境，以及 prompt-injection 尝试，必须留在本地或被 blocked-private 拦截。

## Route Classes

| Route class | Meaning | Cloud payload policy |
| --- | --- | --- |
| local-first / local-only | 本地 Qwen 或本地工具即可处理，或任务包含私有上下文。 | 不发送 cloud payload。 |
| redacted-cloud / cloud_allowed_redacted | 公共复杂任务需要云端辅助，但原始上下文需先脱敏和压缩。 | 只发送 redacted/summary payload，不发送 private raw content。 |
| blocked-private / cloud_blocked_private | 请求包含私有原文、未授权路径或 prompt-injection 风险。 | 禁止上云，记录本地 trace。 |

## Evidence

当前 130 个 synthetic NAS benchmark 的核心结果为：average_reduction_ratio = 92.68%（0.926837），cloud_call_avoidance_rate = 61.54%（0.615385），private_leak_count = 0，quality_pass_rate = 100%。这说明在已覆盖的 benchmark 场景中，路由减少了不必要的云端输入，并且没有把私有 NAS 原文送入 cloud payload。

## Remaining Validation

这些数字仍属于 benchmark 证据，不是长期生产统计。后续需要执行 7-day local-only token trace，记录每类任务的 naive cloud tokens、optimized cloud tokens、route decision、redaction_applied、quality sample result 和云端调用状态；在选定真实 cloud provider 和价格模型之后，再计算真实成本趋势。
