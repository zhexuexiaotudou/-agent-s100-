# Token Cost Safe Wording

## 可以写

- 系统在上云前使用真实 Qwen tokenizer 进行 token 预算统计。
- 系统通过本地隐私脱敏、上下文压缩和 local-first 路由减少不必要的云端输入 token。
- 100 个 synthetic NAS benchmark 中，平均云端输入 token 降幅为 0.927，private_leak_count = 0。
- private/ACL denied/prompt-injection 场景 fail closed，不把原始 NAS 私有内容发送到 cloud payload。

## 不应写

- 真实账单成本已显著下降。
- 所有任务都不需要云端。
- 脱敏后完全无隐私风险。
- Qwen 可以直接执行工具或绕过 allowlist dispatcher。
