# Tokenizer / Token Budget Design Report Section

本项目将 Token Budget & Privacy Router 接入 OpenClaw + Qwen2.5 local gateway + Workspace Harness 路径。每个可能上云的请求先使用真实 Qwen tokenizer 统计 token，然后执行隐私脱敏、上下文压缩和 local-first 路由判断。130 个 synthetic NAS benchmark 中，平均 naive cloud tokens 为 1240.65，平均 optimized cloud tokens 为 119.81，平均云端输入 token 降幅为 92.68%（0.926837），cloud_call_avoidance_rate 为 61.54%（0.615385），private_leak_count = 0，quality_pass_rate = 100%。

该指标只代表本项目 benchmark 中的云端输入 token 对照，不代表真实账单成本下降或长期生产统计。真实成本趋势仍需接入生产 trace、云 API 价格模型、缓存/重试统计和长期质量抽样后再判断。
