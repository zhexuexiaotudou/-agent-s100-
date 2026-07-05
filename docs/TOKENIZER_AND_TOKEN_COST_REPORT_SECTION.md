# Tokenizer 与云端 token 消耗报告段落

系统在上云前加入本地 Token Budget & Privacy Router：先用 Qwen2.5 tokenizer 统计用户请求和 NAS 上下文 token，再执行隐私脱敏、上下文压缩和本地优先路由。100 个 NAS 场景 benchmark 显示，naive baseline 平均云端输入 token 为 1240.65，optimized 路径平均云端输入 token 为 119.81，平均降幅为 0.927，中位降幅为 1.000，p90 降幅为 1.000。

该结果支持的安全表述是：系统在 benchmark 中通过本地 tokenizer、隐私脱敏、上下文裁剪和路由判断，benchmark 中显著减少云端输入 token，并保持 private_leak_count = 0。这里的 token 降耗是云端输入 token 对照，不等同于真实账单成本下降。
