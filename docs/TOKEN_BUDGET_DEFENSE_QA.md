# Token Budget Defense QA

Q: 是否使用了真实 tokenizer？

A: 是。报告记录 `real_qwen_tokenizer_used = True`，tokenizer identity hash 为 `8695d2b54075568a870d2364c50a53a59be11e28305a1cf4cc5bdbb67a7223af`。

Q: benchmark 规模和核心指标是多少？

A: 当前统一口径为 130 个 synthetic NAS benchmark cases。平均云端输入 token 降幅为 92.68%（0.926837），cloud_call_avoidance_rate 为 61.54%（0.615385），private_leak_count = 0，quality_pass_rate = 100%。

Q: 是否可以写真实账单成本下降？

A: 不可以。当前数据来自 benchmark 的云端输入 token 对照，不包含真实云 API 价格、调用日志、缓存命中和重试成本。

Q: cloud 是否看到私有 NAS 原文？

A: 本轮 gate 的 private_leak_count = 0，cloud_private_egress_count = 0。redaction_map 只保留在本地 trace，不进入 cloud payload。

Q: Qwen 是否获得工具执行权？

A: 没有。Qwen 只参与本地理解/路由判断，工具执行仍受 allowlist dispatcher 和 Harness policy 控制。
