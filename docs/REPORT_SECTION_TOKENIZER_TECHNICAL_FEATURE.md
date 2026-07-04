# Report Section: Tokenizer Technical Feature

## Summary

本项目在 OpenClaw + Qwen2.5 local gateway + Workspace Harness 路径中加入 Token Budget & Privacy Router，使每个可能上云的请求先经过本地 token 预算、隐私脱敏、上下文压缩和路由判断。该模块的目标不是替代 OpenClaw 或赋予 Qwen 工具执行权，而是在受控 Harness 边界内减少不必要的云端输入，并阻止私有 NAS 原文进入 cloud payload。

## Technical Features

1. 真实 Qwen tokenizer：系统使用从 Qwen2.5-1.5B tokenizer 文件加载的 tokenizer 统计 token，当前 tokenizer backend 为 `tokenizers_json`，`real_qwen_tokenizer_used = true`，`fallback_used = false`，tokenizer identity hash 为 `8695d2b54075568a870d2364c50a53a59be11e28305a1cf4cc5bdbb67a7223af`。

2. 隐私脱敏：在 cloud route 前，本地 redactor 识别 NAS 路径、私有文件名、联系方式、证件号、secret、ACL denied 语境和 prompt-injection 语境。cloud payload 只允许 public 或 redacted 内容，redaction map 留在本地 trace，不随 payload 外发。

3. 上下文压缩：对文档问答、报告生成、文件整理建议等长上下文任务，系统在上云前保留任务目标、必要摘要、允许公开的元信息和可解释 trace 字段，删除私有原文和冗余上下文，从而降低 cloud input tokens。

4. local-first / redacted-cloud / blocked-private 路由：简单检索、文件夹摘要、私有语境和 ACL denied 请求优先留在本地；公共复杂任务可进入 redacted-cloud；私有原文、未授权路径和 prompt-injection 场景进入 blocked-private 或 local-only 路径。

5. token trace：Harness 记录每次预算决策的 token 估算、脱敏状态、压缩前后规模、路由结果和 run_id，用于后续审计与生产 trace 对比。trace 不记录 private raw content，不把 redaction map 发送给 cloud。

## Boundary

当前证据支持“benchmark 中云端输入 token 明显减少”和“private_leak_count = 0”。这些结果不能写成真实账单成本下降，也不能写成长期生产统计；真实成本趋势仍需后续生产 trace 和云 API 价格模型验证。
