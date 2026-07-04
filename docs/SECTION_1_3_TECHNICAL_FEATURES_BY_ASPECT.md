# 1.3 Technical Features By Aspect

## Token Budget and Privacy Router

本作品在 OpenClaw + Qwen + Workspace Harness 路径前增加 Token Budget & Privacy Router。它使用真实 Qwen tokenizer 统计 token，先脱敏 NAS 路径、私有文件名、联系方式、证件号和 secret，再按任务类型进行上下文裁剪和路由判断。benchmark 中 private_leak_count = 0，平均云端输入 token 降幅 = 0.927。
