# Baseline Tracking

本文把 baseline 拆成 Codex 可跟踪的任务。每个任务都应开 GitHub issue，或者至少在本文中更新状态。

状态定义：

| 状态 | 含义 |
| --- | --- |
| `todo` | 尚未开始 |
| `doing` | 正在实机验证 |
| `blocked` | 被硬件、网络、权限或依赖阻塞 |
| `verified` | 已通过验收并有证据 |
| `dropped` | 明确不进当前 baseline |

## Epic A：S100P PC Parity

| ID | 标题 | 状态 | DoD |
| --- | --- | --- | --- |
| A-001 | S100P 硬件/系统盘点 | doing | 记录 Ubuntu、kernel、架构、磁盘、网络、Node/npm、OpenClaw 状态 |
| A-002 | RDK Studio 部署 OpenClaw Gateway | doing | Gateway 可启动，Control UI 可访问，重启后恢复 |
| A-003 | NAS workspace 挂载到 S100P | todo | S100P 可读写 NAS，重启后自动挂载 |
| A-004 | WebChat/Telegram smoke test | todo | 消息能触发命令并返回状态 |
| A-005 | 工具执行 allowlist | todo | 只允许执行 `scripts/` 下白名单脚本 |
| A-006 | Docker / sandbox 验证 | todo | 非主会话不能写宿主机敏感路径 |
| A-007 | Browser automation smoke test | todo | 能打开测试网页、截图、保存到 NAS |
| A-008 | ROS2 status 工具 | todo | OpenClaw 能查询 ROS2 node/topic/service |
| A-009 | ROS bag 采集工具 | todo | 聊天命令能开始/停止采集，并写入 NAS |
| A-010 | 7x24 稳定性测试 | todo | 连续运行 7 天，记录重启、内存、磁盘、日志 |

## Epic B：AI NAS Homework

| ID | 标题 | 状态 | DoD |
| --- | --- | --- | --- |
| B-001 | NAS 资料库目录规范 | todo | 定义 documents/photos/videos/robot_datasets/logs/reports |
| B-002 | 文档索引和摘要 | todo | 对 NAS 文档生成索引和每日摘要 |
| B-003 | 图片 caption baseline | todo | 对图片生成 caption，支持文本搜索 |
| B-004 | 机器人数据集 card | todo | 每次采集自动生成 dataset card |
| B-005 | 日志分析助手 | todo | 给定日志目录，输出失败摘要、关键错误、建议命令 |
| B-006 | GitHub/Codex workflow | todo | issue -> branch -> PR -> Codex review 链路可走 |
| B-007 | 周报/实验报告生成 | todo | 从 NAS 日志和数据集生成 Markdown 周报 |
| B-008 | Home Assistant / 设备只读状态 | todo | 只查询状态，不做控制 |
| B-009 | 低风险自动化控制 | todo | 白名单 + 二次确认 + 审计日志 |
| B-010 | 安全审计清单 | todo | 检查 token、NAS 权限、Gateway 暴露、sandbox |

## 当前最近事实

- Windows 共享网络已使 S100P 通过 `192.168.137.10` 上网。
- S100P 已手动安装 Node.js `v20.19.2` arm64 tarball，并修正 `/usr/bin/node` 链接后 `node -v` 成功。
- 下一步应回到 RDK Studio，用 `root@192.168.137.10:22` 重新连接并部署 OpenClaw。

## Codex 每次更新 issue 时应补充

- 当前板端 IP。
- 当前执行用户。
- 是否使用 Windows ICS 共享网络。
- OpenClaw 页面状态截图。
- 关键命令输出。
- 失败日志路径。
- 是否需要 GPT Pro 复审。
