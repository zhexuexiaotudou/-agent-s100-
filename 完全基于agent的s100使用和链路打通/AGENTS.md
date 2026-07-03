# Codex 工作约定

这个仓库由 Codex 负责执行、记录和复盘。GPT Pro 或其他更强模型只作为阶段性架构评审输入，不直接替代仓库中的可执行证据。

## 默认工作方式

1. 先读 `README.md`，再读当前任务相关的 `docs/` 文档。
2. 涉及 S100P 实机操作时，先确认网络、SSH、板端 IP 和当前用户。
3. 涉及 OpenClaw + NAS baseline 时，先读：
   - `docs/openclaw_s100p_nas_baseline.md`
   - `docs/baseline_tracking.md`
   - `docs/pro_model_handoff.md`
4. 修改后必须把新成功路径或失败路径沉淀回仓库。

## Codex 和 GPT Pro 分工

Codex 负责：

- 执行命令、连板子、改脚本、改文档。
- 维护 GitHub issue、PR、验收记录和证据。
- 把实测结果写入 `docs/`。
- 控制权限边界，不扩大 NAS 和机器人控制权限。

GPT Pro 负责：

- 阶段性审阅架构和 baseline 是否合理。
- 帮助比较 S100P、NAS、PC 的角色边界。
- 帮助拆分高价值功能和低价值探索项。
- 对 Codex 已经收集的证据做二次判断。

## 证据要求

每个 baseline 任务完成时至少记录：

- 运行环境：S100P 系统、OpenClaw 版本、NAS 型号和共享路径。
- 操作步骤：命令或 RDK Studio 操作。
- 验收结果：截图、日志路径或命令输出。
- 风险：权限、安全、重启后是否保持。
- 后续：是否需要 GPT Pro 复审。

## 禁止事项

- 不把 Gateway 裸露到公网。
- 不让 OpenClaw 直接访问整个 NAS。
- 不在第一版 baseline 承诺本地大模型。
- 不允许未白名单的机器人控制动作。
- 不把聊天里的假设写成“已验证事实”。
