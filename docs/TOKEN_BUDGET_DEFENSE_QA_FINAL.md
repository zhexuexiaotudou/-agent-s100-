# Token Budget Defense QA Final

## 1. 你们怎么统计 token？

我们使用真实 Qwen tokenizer 统计 token，而不是用字符数或通用近似规则替代。当前记录为 `real_qwen_tokenizer_used = true`、`fallback_used = false`、backend = `tokenizers_json`，tokenizer identity hash 为 `8695d2b54075568a870d2364c50a53a59be11e28305a1cf4cc5bdbb67a7223af`。每个可能上云的请求都会记录 naive cloud tokens、optimized cloud tokens、脱敏状态、压缩状态和 route decision。

## 2. 为什么说减少 token？

因为 benchmark 同一批任务同时计算了 naive cloud input tokens 和经过本地脱敏、上下文压缩、local-first 路由后的 optimized cloud input tokens。130 个 synthetic NAS benchmark 中，平均云端输入 token 降幅为 92.68%（0.926837），中位降幅为 100%，P90 降幅为 100%。

## 3. 这个是不是等于省钱？

不是。当前结果只能说明 benchmark 中 cloud input tokens 减少，不等同于真实账单成本下降。真实账单还取决于 cloud provider 价格、input/output token 单价、缓存命中、重试、长上下文计费、实际调用比例和质量返工成本。报告中应写“benchmark 云端输入 token 明显减少”，不能写“真实账单成本已显著下降”。

## 4. 如果 cloud 需要处理复杂任务怎么办？

公共复杂任务可以进入 redacted-cloud 路径。系统先在本地用 Qwen tokenizer 估算 token，再进行隐私脱敏和上下文压缩，只把必要的公开摘要、任务目标和允许公开的元信息发送给 cloud。cloud 只作为 overflow，不是默认路径。

## 5. 私有内容会不会上云？

在当前 gate 和 benchmark 中，private_leak_count = 0，cloud_private_egress_count = 0。私有 NAS 原文、ACL denied 路径、家庭/财务/证件/secret 等敏感内容，以及 prompt-injection 风险，会被 local-only 或 blocked-private 拦截。redaction map 只保留在本地 trace，不进入 cloud payload。

## 6. 为什么有些任务 optimized tokens 是 0？

optimized tokens 为 0 通常表示该任务被 local-only 处理或 blocked-private 拦截，不需要发送 cloud payload。这不是 token 统计失败，而是路由决策让 cloud input 变为 0。例如简单 NAS 检索、文件夹摘要、ACL denied 和明显私有请求都可能出现 optimized cloud tokens = 0。

## 7. benchmark 是真实生产数据吗？

不是。当前 130 个 cases 是 synthetic NAS benchmark，用于覆盖 NAS 搜索、中文/中英混合查询、文档问答、文件夹摘要、报告生成、文件整理建议、private ACL denied、cloud-sensitive mixed、prompt injection 和 public research 等场景。它验证的是产品路由与隐私控制逻辑，不代表长期生产流量分布。

## 8. 未来怎么验证真实成本？

下一步执行 7-day local-only production trace。trace 只记录 token 数、任务类型、route decision、脱敏/压缩标志、质量抽样结果和 cloud eligibility，不记录 private raw content。等真实 cloud provider 和价格模型确定后，再用生产 trace 计算成本趋势，并结合质量抽样确认 token 缩减没有牺牲任务可用性。
