# Function and Features Safe Version

- 已验证：S100P 上的 OpenClaw/Qwen 服务路径、网页入口、健康检查和模型身份查询。
- 已验证：权限感知搜索、文档 RAG、文件夹摘要、证据报告、case packet 等只读 AI-NAS 工具链。
- 已验证：工具调用经过 allowlist dispatcher，Qwen 不拥有直接工具执行权。
- 已验证：私有内容脱敏、cloud egress 拦截、prompt injection 拒绝和 trace/audit 记录。
- 原型验证：sandbox 写入 canary、审批 token、dry-run planner 和回滚恢复。
- 需降级：手机端只能写为支持基础浏览器访问和结构化 PWA/mobile gate，完整登录后移动工作流截图仍需补充。
- 不开放：真实 NAS 删除、移动、权限修改和自动写入。
