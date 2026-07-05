# Unsupported or Overclaimed Phrases

Replace or remove the following before using the description in a formal report:

- Unsafe: 真实 NAS 写操作已安全开放。
  Safe: 真实 NAS 写操作仍锁定；当前只支持只读 AI-NAS 和 sandbox/dry-run 写入治理验证。
- Unsafe: Dream7B 是当前 OpenClaw AI-NAS 前台模型能力。
  Safe: Dream7B 是历史 runtime/研究证据，不作为当前 AI-NAS 前台产品能力；当前产品路径是 Qwen + OpenClaw。
- Unsafe: 手机端所有复杂工作流都已完整验收。
  Safe: 支持手机浏览器访问基础入口；已有 PWA/mobile 结构 gate，当前包含移动视口截图。
- Unsafe: 系统已自动整理真实 NAS 文件。
  Safe: 系统可生成文件整理/写操作 dry-run 方案、审批和回滚计划；真实移动/删除仍未开放。
- Unsafe: 已证明大幅降低真实账单成本。
  Safe: 有本地脱敏与字符启发式 token 估算，支持‘减少不必要云端 token 消耗’。
