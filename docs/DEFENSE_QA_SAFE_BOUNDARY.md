# Defense QA Safe Boundary

Q: token 成本是否已经真实降低？

A: 当前证据支持“benchmark 中云端输入 token 减少”，不支持直接写成真实账单成本下降。真实账单还需要具体云模型价格、实际调用日志、缓存命中和失败重试统计。

Q: cloud 是否能看到 NAS 私有原文？

A: 本轮 benchmark 和 redactor gate 中 private_leak_count = 0。设计上 redaction_map 只保留在本地 trace，不进入 cloud payload。

Q: Qwen 是否可以直接执行 NAS 工具？

A: 不可以。Qwen 只做本地理解、摘要和路由判断；工具执行仍受 allowlist dispatcher 和 Harness policy 控制。
