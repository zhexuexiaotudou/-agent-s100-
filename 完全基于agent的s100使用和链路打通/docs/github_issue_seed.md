# GitHub Issue Seed

GitHub 连接器不可用时，先把 issue 内容保存在这里。后续可以手动复制到 GitHub，或用 `gh issue create` 批量导入。

## Issue 1

Title:

```text
Epic A: S100P PC parity baseline
```

Body:

```markdown
## Goal
验证 S100P 是否能实现 PC 上 OpenClaw 的核心类似效果。

## Scope
- Gateway / Chat / 控制面
- 基础工具执行面
- NAS workspace 挂载
- 轻量浏览器、Git、Python、ROS2 status

## Out of Scope
- 完整替代 x86 PC
- 第一版本地大模型
- 裸公网暴露 Gateway

## Tracking Source
- `docs/openclaw_s100p_nas_baseline.md`
- `docs/baseline_tracking.md`

## Initial Tasks
- [ ] A-001 S100P 硬件/系统盘点
- [ ] A-002 RDK Studio 部署 OpenClaw Gateway
- [ ] A-003 NAS workspace 挂载到 S100P
- [ ] A-004 WebChat/Telegram smoke test
- [ ] A-005 工具执行 allowlist
- [ ] A-006 Docker / sandbox 验证
- [ ] A-007 Browser automation smoke test
- [ ] A-008 ROS2 status 工具
- [ ] A-009 ROS bag 采集工具
- [ ] A-010 7x24 稳定性测试

## Codex Instructions
按仓库文档执行，所有完成项必须有命令输出、截图或日志路径。不要扩大 NAS 权限，不要跳过安全模型。
```

## Issue 2

Title:

```text
Epic B: AI NAS homework baseline
```

Body:

```markdown
## Goal
复刻高价位 AI NAS / OpenClaw NAS 的产品功能层，而不是复制昂贵硬件。

## Scope
- 私有资料库
- 语义照片/视频整理
- 机器人数据集管家
- 日志分析助手
- GitHub/Codex workflow
- 周报和实验报告
- 多 agent 分工

## Tracking Source
- `docs/openclaw_s100p_nas_baseline.md`
- `docs/baseline_tracking.md`

## Initial Tasks
- [ ] B-001 NAS 资料库目录规范
- [ ] B-002 文档索引和摘要
- [ ] B-003 图片 caption baseline
- [ ] B-004 机器人数据集 card
- [ ] B-005 日志分析助手
- [ ] B-006 GitHub/Codex workflow
- [ ] B-007 周报/实验报告生成
- [ ] B-008 Home Assistant / 设备只读状态
- [ ] B-009 低风险自动化控制
- [ ] B-010 安全审计清单

## Codex Instructions
先抄产品功能层，不把本地大模型放进第一版 baseline。每个功能必须有验收标准和安全边界。
```

## Issue 3

Title:

```text
Security: OpenClaw + S100P + NAS minimum permission model
```

Body:

```markdown
## Goal
建立 OpenClaw + S100P + TS-264C NAS 的第一版安全模型。

## Tracking Source
- `docs/security_model.md`

## Requirements
- [ ] Gateway 只允许 LAN 或 Tailscale 访问
- [ ] NAS 只开放 `/OpenClawWorkspace` 专用共享
- [ ] OpenClaw 使用独立 NAS 账号，不用管理员账号
- [ ] token 不写入 Git
- [ ] 工具执行使用 allowlist
- [ ] 机器人控制动作默认禁止，后续需要白名单和二次确认
- [ ] 形成可重复执行的安全检查脚本

## Codex Instructions
安全策略默认保守。任何扩大权限的改动都必须单独开 issue，并标记为 experiment。
```

## Issue 4

Title:

```text
Current: Finish RDK Studio OpenClaw deployment on S100P
```

Body:

```markdown
## Goal
完成当前 S100P 上 OpenClaw 的 RDK Studio 部署。

## Current Facts
- Windows ICS 共享网络已打通。
- Windows ethernet IP: `192.168.137.1`。
- S100P current IP: `192.168.137.10`。
- S100P 能 ping 通 `8.8.8.8` 和 `baidu.com`。
- Node.js arm64 tarball 已安装到 `/opt/node-v20.19.2-linux-arm64`。
- `/usr/bin/node`、`/usr/bin/npm`、`/usr/bin/npx` 已指向 Node 20。
- `node -v` 已成功。

## Next Steps
- [ ] 在 RDK Studio 中重新添加 `root@192.168.137.10:22`
- [ ] 进入 OpenClaw 页面重新部署
- [ ] 记录部署日志
- [ ] 验证 `openclaw-gateway.service` 状态
- [ ] 验证 Control UI 可访问
- [ ] 把成功流程写回 docs

## Codex Instructions
优先使用 RDK Studio 部署，不手工绕开 OpenClaw 安装流程。失败时保留日志和截图。
```
